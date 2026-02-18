# INFRA-059: Impact-to-Journey Mapping

## State

ACCEPTED

## Goal Description

Implement automatic mapping of code changes to user journeys, enabling targeted regression testing and richer risk analysis during preflight checks. Build a reverse index from `implementation.files[]` patterns in journey YAMLs to journey IDs, cache it in SQLite, and surface "Affected Journeys" in both `agent impact` and `agent preflight`.

## Linked Journeys

- JRN-007: Implement Agent Impact Command
- JRN-044: Introduce User Journeys as First-Class Artifacts
- JRN-054: Impact-to-Journey Mapping

## Panel Review Findings

**@Architect**:

- PASS. New `agent/db/journey_index.py` module sits in the Infrastructure layer — correct per `architectural-standards.mdc` layer map (`db` → imports from `core`, stdlib only).
- Reverse index cached in SQLite via existing `agent/db/` layer. No new DB dependency.
- ADR-025 compliance: `journey_index` module imported lazily inside `impact()` and `preflight()`.
- Staleness via `mtime` comparison aligns with the lazy-rebuild pattern used elsewhere.
- `journey_file_index` table schema: `(file_pattern TEXT, journey_id TEXT, journey_title TEXT, updated_at REAL, PRIMARY KEY(file_pattern, journey_id))`.

**@Backend**:

- PASS. All public functions must have full type hints per `architectural-standards.mdc` §2.
- `impact()` already uses Typer (not Click) — implementation must add `--rebuild-index` and `--json` as `typer.Option()` params.
- Hybrid matching logic (`fnmatch` + `Path.name` fallback) is correct for backward compatibility with bare filenames in legacy journeys.
- `yaml.safe_load()` for journey parsing. Parameterized SQLite queries throughout.
- Per ADR-028, Typer CLI commands are synchronous — `subprocess.run` is correct.

**@QA**:

- PASS. Test strategy covers 9 unit tests + 3 integration tests. Comprehensive edge cases: glob matching, bare filenames, empty `files: []`, staleness detection, path traversal, deduplication, ungoverned files.
- Tests must use `tmp_path` fixture with synthetic journey YAMLs and an in-memory or temp SQLite DB.
- Integration tests verify end-to-end CLI output via `CliRunner`.

**@Security**:

- PASS (with conditions). All path operations validated with `Path.resolve()` + `is_relative_to(repo_root)` at index build time — symlink traversal caught. `yaml.safe_load()` prevents arbitrary code execution. SQLite queries use `?` parameterization.
- Condition: Journey YAML content is never sent to external services during index build. AI mode (`--ai`) scrubs data via existing `scrub_sensitive_data()` before prompt inclusion.

**@Observability**:

- PASS. OpenTelemetry span `journey_index.rebuild` as child of `impact` span. Attributes: `journey_count`, `file_glob_count`, `rebuild_duration_ms`, `cache_status` (`hit`/`miss`/`force_rebuild`).
- Index rebuild duration printed to stdout. `--json` output includes `rebuild_timestamp`.

**@Compliance**:

- PASS. Index rebuilds logged to audit log for SOC 2 CC7.1 traceability. `rebuild_timestamp` in JSON output provides audit trail. Apache 2.0 license header on all new files.

**@Docs**:

- PASS. CHANGELOG.md updated with new `agent impact --rebuild-index` and `--json` flags. README section on impact analysis updated.

**@Product**:

- PASS. "Affected Journeys" Rich table with copy-pasteable `pytest -m "journey(...)"` command is actionable. "Ungoverned file" warning suggests `agent journey backfill-tests` remediation.

**@Mobile** / **@Web**: No concerns — this is backend/CLI only.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Add type hints to all new public functions
- [ ] Ensure consistent Rich console formatting
- [ ] Use `config.journeys_dir` consistently (not hardcoded paths)

## Implementation Steps

### Step 1: Create `agent/db/journey_index.py` [NEW]

New infrastructure module for the journey reverse index.

```python
# agent/db/journey_index.py
"""Journey file reverse index for impact-to-journey mapping."""

import fnmatch
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml  # ADR-025: local import in callers

JOURNEY_INDEX_TABLE = "journey_file_index"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {JOURNEY_INDEX_TABLE} (
    file_pattern TEXT NOT NULL,
    journey_id TEXT NOT NULL,
    journey_title TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL,
    PRIMARY KEY (file_pattern, journey_id)
)
"""


def ensure_table(conn: sqlite3.Connection) -> None:
    """Create the journey_file_index table if it doesn't exist."""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def rebuild_index(
    conn: sqlite3.Connection,
    journeys_dir: Path,
    repo_root: Path,
) -> Dict[str, Any]:
    """Rebuild the journey file reverse index from journey YAMLs.

    Returns dict with keys: journey_count, file_glob_count,
    rebuild_duration_ms, warnings.
    """
    start = time.monotonic()
    warnings: List[str] = []

    ensure_table(conn)
    conn.execute(f"DELETE FROM {JOURNEY_INDEX_TABLE}")

    journey_count = 0
    file_glob_count = 0

    if not journeys_dir.exists():
        conn.commit()
        return {
            "journey_count": 0,
            "file_glob_count": 0,
            "rebuild_duration_ms": 0.0,
            "warnings": [],
        }

    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            state = (data.get("state") or "DRAFT").upper()
            if state not in ("COMMITTED", "ACCEPTED"):
                continue

            jid = data.get("id", jfile.stem)
            title = data.get("title", "")
            files = data.get("implementation", {}).get("files", [])

            if not files:
                continue

            journey_count += 1
            now = time.time()
            pattern_count = 0

            for pattern in files:
                # Path scoping: reject absolute and traversal
                p = Path(pattern)
                if p.is_absolute():
                    warnings.append(f"{jid}: Absolute path rejected: '{pattern}'")
                    continue
                try:
                    resolved = (repo_root / p).resolve()
                    resolved.relative_to(repo_root.resolve())
                except ValueError:
                    warnings.append(f"{jid}: Path traversal rejected: '{pattern}'")
                    continue

                conn.execute(
                    f"INSERT OR REPLACE INTO {JOURNEY_INDEX_TABLE} "
                    "(file_pattern, journey_id, journey_title, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (pattern, jid, title, now),
                )
                pattern_count += 1

            file_glob_count += pattern_count

            # Warn on overly broad patterns (AC-9)
            if pattern_count > 100:
                warnings.append(
                    f"{jid}: {pattern_count} patterns indexed (may be overly broad)"
                )

    conn.commit()
    duration_ms = (time.monotonic() - start) * 1000

    return {
        "journey_count": journey_count,
        "file_glob_count": file_glob_count,
        "rebuild_duration_ms": duration_ms,
        "warnings": warnings,
    }


def is_stale(conn: sqlite3.Connection, journeys_dir: Path) -> bool:
    """Check if the index is stale by comparing journey YAML mtimes."""
    ensure_table(conn)
    row = conn.execute(
        f"SELECT MAX(updated_at) FROM {JOURNEY_INDEX_TABLE}"
    ).fetchone()
    last_updated = row[0] if row and row[0] else 0.0

    if not journeys_dir.exists():
        return False

    for scope_dir in journeys_dir.iterdir():
        if not scope_dir.is_dir():
            continue
        for jfile in scope_dir.glob("JRN-*.yaml"):
            if os.path.getmtime(jfile) > last_updated:
                return True
    return False


def get_affected_journeys(
    conn: sqlite3.Connection,
    changed_files: List[str],
    repo_root: Path,
) -> List[Dict[str, Any]]:
    """Match changed files against indexed patterns. Returns deduplicated list."""
    ensure_table(conn)

    rows = conn.execute(
        f"SELECT file_pattern, journey_id, journey_title FROM {JOURNEY_INDEX_TABLE}"
    ).fetchall()

    # Build pattern → journey map
    matches: Dict[str, Dict[str, Any]] = {}  # jid → {id, title, matched_files}

    for pattern, jid, title in rows:
        for changed in changed_files:
            # Hybrid matching (AC-8)
            matched = fnmatch.fnmatch(changed, pattern)
            if not matched:
                matched = Path(changed).name == pattern
            if matched:
                if jid not in matches:
                    matches[jid] = {
                        "id": jid,
                        "title": title,
                        "matched_files": [],
                    }
                if changed not in matches[jid]["matched_files"]:
                    matches[jid]["matched_files"].append(changed)

    # Attach test files from journey YAMLs
    journeys_dir = repo_root / ".agent" / "cache" / "journeys"
    for jid, info in matches.items():
        info["tests"] = _get_journey_tests(journeys_dir, jid)

    return sorted(matches.values(), key=lambda j: j["id"])


def _get_journey_tests(journeys_dir: Path, jid: str) -> List[str]:
    """Look up implementation.tests for a journey ID."""
    if not journeys_dir.exists():
        return []
    for scope_dir in journeys_dir.iterdir():
        if not scope_dir.is_dir():
            continue
        for jfile in scope_dir.glob("JRN-*.yaml"):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if isinstance(data, dict) and data.get("id") == jid:
                return data.get("implementation", {}).get("tests", [])
    return []
```

### Step 2: Add schema to `agent/db/schema.sql` [MODIFY]

Append the `journey_file_index` table DDL to the existing schema file.

### Step 3: Modify `agent/commands/check.py` — `impact()` function [MODIFY]

Insert journey impact mapping after the existing `DependencyAnalyzer.find_reverse_dependencies()` call (~line 1090):

1. Add `--rebuild-index` and `--json` Typer options to the `impact()` function signature.
2. After the static dependency analysis block, add:
   - Lazy import of `journey_index` module (ADR-025)
   - Open SQLite connection to `config.db_path`
   - Check staleness or `--rebuild-index` flag → call `rebuild_index()`
   - Call `get_affected_journeys()` with `changed_files`
   - Render "Affected Journeys" Rich table (Journey ID, Title, Matched Files, Test File)
   - Render copy-pasteable `pytest -m "journey(...)"` command
   - Render "Ungoverned files" warnings with `backfill-tests` suggestion
3. If `--json` flag, output full report as JSON including `affected_journeys` array and `rebuild_timestamp`.
4. If `--ai` flag, include affected journey context in the AI prompt.

### Step 4: Modify `agent/commands/check.py` — `preflight()` function [MODIFY]

After the existing journey coverage check (~line 680), add impact-to-journey targeted test identification:

1. Lazy import `journey_index`
2. Get changed files from git diff
3. Auto-rebuild index if stale (silent first run)
4. Call `get_affected_journeys()`
5. Output required journey test markers as copy-pasteable pytest command

### Step 5: Create tests `agent/tests/db/test_journey_index.py` [NEW]

Unit tests covering:

- `test_rebuild_index` — temp dir with journey YAMLs, verify DB rows
- `test_get_affected_journeys_glob` — `fnmatch` matches `src/agent/**/*.py`
- `test_get_affected_journeys_bare_filename` — `check.py` matches via `Path.name` fallback
- `test_empty_implementation_files` — no index entries, no error
- `test_staleness_detection` — mock `os.path.getmtime`, verify rebuild trigger
- `test_path_traversal_rejection` — `../../etc/passwd` rejected
- `test_ungoverned_file` — no journey match produces warning
- `test_deduplication` — overlapping globs deduplicate by journey ID
- `test_overly_broad_pattern_warning` — >100 patterns warns

### Step 6: Create integration tests `agent/tests/commands/test_impact_journeys.py` [NEW]

- `test_impact_shows_affected_journeys` — CLI output includes Rich table
- `test_impact_json_output` — `--json` includes `affected_journeys` array
- `test_preflight_journey_test_command` — preflight outputs pytest marker command

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/db/test_journey_index.py` — 9 unit tests pass
- [ ] `pytest .agent/tests/commands/test_impact_journeys.py` — 3 integration tests pass
- [ ] `pytest .agent/tests/commands/` — all existing tests still pass (no regressions)

### Manual Verification

- [ ] `agent impact INFRA-059 --base HEAD~1` outputs "Affected Journeys" Rich table
- [ ] `agent impact INFRA-059 --json` outputs JSON with `affected_journeys` array
- [ ] `agent impact INFRA-059 --rebuild-index` forces full index rebuild
- [ ] `agent preflight` shows required journey tests with pytest command
- [ ] First run without index auto-builds silently

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with `--rebuild-index` and `--json` flags
- [ ] README.md impact section updated

### Observability

- [ ] Structured logs free of PII
- [ ] OTel span `journey_index.rebuild` with attributes

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed
- [ ] Existing tests unbroken
