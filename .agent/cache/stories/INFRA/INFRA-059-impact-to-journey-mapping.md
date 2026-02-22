# INFRA-059: Impact-to-Journey Mapping

## State

COMMITTED

## Problem Statement

The `env -u VIRTUAL_ENV uv run agent impact` command identifies files touched by a changeset but doesn't map them to the user journeys those files support. A developer can modify `journey.py` without knowing it affects JRN-044's behavioral contract, and preflight has no way to flag that the relevant journey tests should run. The missing link between "what changed" and "what could regress" is the root cause of user-facing regressions slipping through governance.

## User Story

As a **developer governed by the agent framework**, I want the impact analysis to automatically identify which user journeys are affected by my changes so that I know which regression tests must pass before merge.

## Acceptance Criteria

- [ ] **AC-1**: `env -u VIRTUAL_ENV uv run agent impact` reads `implementation.files[]` and `implementation.tests[]` from all journey YAMLs (via `yaml.safe_load()`) and builds a reverse index: `file_pattern → [journey IDs]`. Patterns may be globs (`**/check.py`) or bare filenames (`check.py`).
- [ ] **AC-2**: `env -u VIRTUAL_ENV uv run agent impact --story STORY-ID` outputs an "Affected Journeys" Rich table (columns: Journey ID, Title, Matched Files, Test File) listing journeys whose `implementation.files` entries match the changeset.
- [ ] **AC-3**: `env -u VIRTUAL_ENV uv run agent impact --ai` includes affected journey context in the AI prompt for richer risk analysis.
- [ ] **AC-4**: `env -u VIRTUAL_ENV uv run agent preflight` uses the impact-to-journey map to identify which journey tests are *required* for the current changeset and outputs a copy-pasteable `pytest -m "journey(...)"` command.
- [ ] **AC-5**: The journey reverse index is cached in a `journey_file_index` SQLite table and rebuilt lazily when any journey YAML's mtime exceeds the stored `updated_at`.
- [ ] **AC-6**: `env -u VIRTUAL_ENV uv run agent impact --rebuild-index` forces a full index rebuild regardless of staleness.
- [ ] **AC-7**: `env -u VIRTUAL_ENV uv run agent impact --json` outputs the complete impact report as JSON, including an `affected_journeys` array with `id`, `title`, `matched_files` count, and `rebuild_timestamp`.
- [ ] **AC-8**: Hybrid matching — try `fnmatch.fnmatch(changed_file, pattern)` first; fall back to `Path(changed_file).name == pattern` for bare filenames. `Path.resolve()` + `is_relative_to(repo_root)` validates all paths at index build time. Entries resolving outside the project root are rejected with a warning.
- [ ] **AC-9**: Index rebuild warns if any single pattern matches >100 files (indicates overly broad touchpoint).
- [ ] **AC-10**: Impact-to-journey mapping is integrated after the existing `DependencyAnalyzer.find_reverse_dependencies()` call in the `impact()` function (~line 992 in `check.py`).
- [ ] **AC-11**: OpenTelemetry span `journey_index.rebuild` as child of `impact` span, with attributes `journey_count`, `file_glob_count`, `rebuild_duration_ms`, `cache_status` (`hit`/`miss`/`force_rebuild`).
- [ ] **AC-12**: On first invocation with no index, auto-build silently (with `[dim]` status message). No `--rebuild-index` required for first use.
- [ ] **AC-13**: "Ungoverned file" warning suggests `env -u VIRTUAL_ENV uv run agent journey backfill-tests` for remediation.
- [ ] **AC-14**: Index build logs to audit log for SOC 2 traceability. `--json` output includes `rebuild_timestamp`.
- [ ] **Negative Test**: A file change matching no journey produces an "ungoverned file" warning with remediation suggestion.
- [ ] **Negative Test**: A journey with `files: []` or missing `implementation.files` produces no index entries and no error.

## Non-Functional Requirements

- Performance: Reverse index build completes in < 2s for 50 journeys. Batch matching fetches all entries once, matches in Python — no per-file DB queries.
- Accuracy: Hybrid matching — `fnmatch` for glob patterns, bare filename fallback for legacy journey entries. Handles `**/` patterns natively.
- Observability: Impact output includes the mapping rationale (which journey field matched which file). Span attributes include cache hit/miss status. Index rebuild duration logged to stdout.
- Security: All path operations validate `is_relative_to(repo_root)` at index build time. Symlink traversal is caught by `Path.resolve()`. Journey YAMLs parsed with `yaml.safe_load()`. SQLite queries use parameterized statements.

## Panel Advice Applied

- @Architect: **[CRITICAL FIX]** AC-1 corrected from non-existent `touchpoints[].files[]` to actual `implementation.files[]` schema. New `agent/db/journey_index.py` module with `journey_file_index` table. Staleness via mtime comparison.
- @Backend: Hybrid matching — `fnmatch` primary, `Path.name` fallback for bare filenames (existing journeys use `check.py`, not `**/check.py`). Batch matching pattern, lazy imports per ADR-025.
- @Product: Rich table output with copy-pasteable pytest command. `--json` outputs complete report. Auto-build on first run. Actionable ungoverned-file warning.
- @QA: Edge cases — empty `files: []`, bare filenames, overlapping globs (deduplicate by journey ID), binary files in diff (filter), symlink traversal rejection.
- @Security: Path scoping at index build time (not just match time). `yaml.safe_load()`. Symlink traversal caught. Parameterized SQLite.
- @Observability: Span hierarchy — `journey_index.rebuild` nested under `impact`. Cache status attribute. Rebuild duration in stdout.
- @Compliance: Journey coverage metric for audit output. Log index rebuilds to audit log. `rebuild_timestamp` in JSON output.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-025 (Lazy AI Service Initialization)

## Linked Journeys

- JRN-007 (Implement Agent Impact Command)
- JRN-044 (Introduce User Journeys as First-Class Artifacts)
- JRN-054 (Impact-to-Journey Mapping)

## Impact Analysis Summary

Components touched:

- `.agent/src/agent/commands/check.py` — integrate journey-scoped test requirement into preflight, add `--rebuild-index` and `--json` flags
- `.agent/src/agent/commands/check.py:impact()` — add affected journeys section after `DependencyAnalyzer` call
- `.agent/src/agent/db/journey_index.py` — [NEW] reverse index build, staleness check, glob matching
- `.agent/src/agent/db/init.py` — add `journey_file_index` table to schema

Workflows affected:

- `/preflight` — targeted test execution based on impact mapping; suggests `pytest -m journey(...)` command
- `/impact` — new "Affected Journeys" output section with rich table

Risks identified:

- Stale index: If journeys are modified without rebuilding the index, mappings may be wrong. Mitigated by mtime-based staleness check on every invocation.
- Over-scoping: Broad globs (e.g., `**/*.py`) could flag too many journeys. Mitigated by warning on >100-file matches.
- Index drift: Journey edits without `--rebuild-index`. Mitigated by automatic rebuild on stale detection.

## Test Strategy

- Unit: `test_rebuild_journey_index()` — temp dir with journey YAMLs, verify DB population.
- Unit: `test_get_affected_journeys()` — changed files match journey patterns.
- Unit: `test_glob_matching()` — `fnmatch` correctly matches `src/agent/**/*.py` patterns.
- Unit: `test_bare_filename_matching()` — changed file `agent/commands/check.py` matches journey entry `check.py` via `Path.name` fallback.
- Unit: `test_empty_implementation_files()` — journey with `files: []` produces no index entries, no error.
- Unit: `test_staleness_detection()` — mock `os.path.getmtime`, verify rebuild trigger.
- Unit: `test_path_traversal_rejection()` — journey entry `../../etc/passwd` rejected at index build time.
- Unit: a file not in any journey produces "ungoverned" warning with remediation suggestion.
- Unit: overlapping globs deduplicate journey results by journey ID.
- Integration: `env -u VIRTUAL_ENV uv run agent impact INFRA-059 --base HEAD~1` outputs "Affected Journeys" Rich table.
- Integration: preflight identifies required journey tests and outputs copy-pasteable pytest command.
- Integration: first-run auto-build creates index without `--rebuild-index`.

## Rollback Plan

- Remove the `journey_file_index` table from the DB schema.
- Revert impact and preflight changes.
- Impact command falls back to file-only output.
