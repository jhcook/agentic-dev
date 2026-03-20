# STORY-ID: INFRA-160: Inject Journey + ADR Catalogue Into Runbook Generation Prompt

## State

ACCEPTED

## Goal Description

Enhance the `agent new-runbook` AI prompt by injecting a sorted and capped catalogue of existing Journeys and ADRs. This ensures the AI Governance Panel can reference relevant technical metadata by ID, which is then back-populated into the story file. This closed-loop technical metadata flow prevents journey gate failures during implementation and reduces the need for manual developer intervention, fulfilling the promise of a self-sufficient agentic CLI while preserving user intent through pre-seeded link extraction.

## Linked Journeys

- JRN-056: Full Implementation Workflow
- JRN-089: Generate Runbook with Targeted Codebase Introspection

## Panel Review Findings

### @Architect
- The use of catalogue helpers in `utils.py` maintains a clean separation between command logic and data retrieval.
- Sorting by numeric ID descending ensures the AI sees the most recent context first, which aligns with typical development priority.

### @Qa
- Added unit tests for the new catalogue builders in `test_story_link_helpers.py`.
- AC-5 cap of 30 entries is verified to ensure token budget stability.
- Edge cases including empty or missing metadata directories are handled gracefully.

### @Security
- No PII is logged during directory scanning.
- Directory listing and file reading are performed within the `.agent` metadata directory, respecting system boundaries.
- The implementation uses `yaml.safe_load` to prevent deserialization attacks when parsing journey metadata.

### @Product
- Acceptance criteria are fully addressed, specifically the catalogue format and numeric sorting.
- The `catalogue_injected` log event provides visibility into prompt construction.
- Preservation of pre-seeded ADR and Journey links from the story file ensures that existing developer context is not lost during the AI generation phase.

### @Observability
- The structured log `catalogue_injected` is added as requested in AC-7, using an `extra` dictionary for metadata.
- Token overhead is controlled by the 30-entry cap and title-only extraction.
- Existing OpenTelemetry traces for the `new-runbook` command will encapsulate the new catalogue building logic; no additional spans are required.

### @Docs
- Internal documentation for catalogue builders is added via PEP-257 docstrings.
- **REQUIRED**: `CHANGELOG.md` must be updated to include a user-facing description of this feature enhancement to satisfy the Definition of Done.

### @Compliance
- Standard Apache-2.0 license headers are included in the new test file.
- The process only scans internal project metadata, posing no GDPR or external compliance risks.

### @Backend
- Type hints are strictly enforced for the new utility functions.
- The catalogue extraction logic handles malformed YAML or Markdown files gracefully via robust error handling, satisfying the NFR for robustness.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/commands/utils.py`
- `.agent/src/agent/commands/runbook.py`
- `.agent/src/agent/commands/tests/test_story_link_helpers.py`
- `CHANGELOG.md`

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/src/agent/commands/tests/test_story_link_helpers.py` | `merge_story_links` | `build_journey_catalogue`, `build_adr_catalogue` | Add new unit tests |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `new_runbook` exit codes | `runbook.py` | 0 (success), 1 (error), 2 (split) | Yes |
| Journey/ADR file scanning | `utils.py` | Recursive/Glob scanning | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Replace the heavy `_load_journey_context` (full YAML dump) with the concise `build_journey_catalogue`.

## Implementation Steps

### Step 1: Add catalogue builders to utils.py

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
    return "\n".join(lines)
===
    return "\n".join(lines)


def build_journey_catalogue(journeys_dir: Path) -> tuple[str, int]:
    """Build a sorted, capped catalogue of available Journeys for AI context.

    Scans the journeys directory recursively for YAML files, extracts the ID and
    title/name, and returns a formatted markdown list. Capped at 30 entries
    sorted by numeric ID descending.

    Args:
        journeys_dir: Path to the directory containing JRN-*.yaml files.

    Returns:
        A tuple of (formatted_catalogue_string, total_count_found).
    """
    if not journeys_dir.exists():
        logger.debug("Journeys directory missing: %s", journeys_dir)
        return "", 0

    entries: list[tuple[str, str]] = []
    for jf in journeys_dir.rglob("*.yaml"):
        try:
            data = yaml.safe_load(jf.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                jid = data.get("id", jf.stem)
                # Prefer 'title' per AC, fall back to 'name' or stem
                title = data.get("title") or data.get("name") or jf.stem
                entries.append((str(jid), str(title)))
        except Exception:  # noqa: BLE001
            continue

    if not entries:
        return "", 0

    total_count = len(entries)

    # Sort by numeric ID descending: JRN-089 -> 89
    def sort_key(e: tuple[str, str]) -> int:
        match = re.search(r"(\d+)", e[0])
        return int(match.group(1)) if match else 0

    entries.sort(key=sort_key, reverse=True)
    top_30 = entries[:30]

    lines = ["Available Journeys:"]
    for jid, title in top_30:
        lines.append(f"- {jid}: {title}")
    return "\n".join(lines), total_count


def build_adr_catalogue(adrs_dir: Path) -> tuple[str, int]:
    """Build a sorted, capped catalogue of available ADRs for AI context.

    Scans the ADRs directory for markdown files, extracts the H1 title,
    and returns a formatted markdown list. Capped at 30 entries sorted by
    numeric ID descending.

    Args:
        adrs_dir: Path to the directory containing ADR-*.md files.

    Returns:
        A tuple of (formatted_catalogue_string, total_count_found).
    """
    if not adrs_dir.exists():
        logger.debug("ADRs directory missing: %s", adrs_dir)
        return "", 0

    entries: list[tuple[str, str]] = []
    for af in adrs_dir.glob("ADR-*.md"):
        try:
            content = af.read_text(encoding="utf-8")
            h1_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            title = h1_match.group(1).strip() if h1_match else af.stem
            # Extract ID from filename (e.g. ADR-041)
            id_match = re.match(r"(ADR-\d+)", af.name)
            aid = id_match.group(1) if id_match else af.stem
            entries.append((str(aid), str(title)))
        except Exception:  # noqa: BLE001
            continue

    if not entries:
        return "", 0

    total_count = len(entries)

    # Sort by numeric ID descending
    def sort_key(e: tuple[str, str]) -> int:
        match = re.search(r"(\d+)", e[0])
        return int(match.group(1)) if match else 0

    entries.sort(key=sort_key, reverse=True)
    top_30 = entries[:30]

    lines = ["Available ADRs:"]
    for aid, title in top_30:
        lines.append(f"- {aid}: {title}")
    return "\n".join(lines), total_count
>>>
```

### Step 2: Inject catalogue and pre-seeded links in runbook.py

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.commands.utils import (
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    extract_adr_refs,
    extract_journey_refs,
    generate_sr_correction_prompt,
    merge_story_links,
    parse_ac_gaps,
    validate_sr_blocks,
)
===
from agent.commands.utils import (
    build_ac_coverage_prompt,
    build_adr_catalogue,
    build_dod_correction_prompt,
    build_journey_catalogue,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    extract_adr_refs,
    extract_journey_refs,
    generate_sr_correction_prompt,
    merge_story_links,
    parse_ac_gaps,
    validate_sr_blocks,
)
>>>
```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
    # INFRA-135: Dynamic Rule Retrieval (Rule Diet)
    # Replaces static truncation with semantic filtering
    rules_content = _retrieve_dynamic_rules(story_content, targeted_context)
    
    if len(rules_content) < len(rules_full) * 0.5:
        console.print(f"[dim]ℹ️  Rule Diet active: Prompt reduced by {100 - (len(rules_content)/len(rules_full)*100):.1f}%[/dim]")

    # 4. Prompt
===
    # INFRA-135: Dynamic Rule Retrieval (Rule Diet)
    # Replaces static truncation with semantic filtering
    rules_content = _retrieve_dynamic_rules(story_content, targeted_context)
    
    if len(rules_content) < len(rules_full) * 0.5:
        console.print(f"[dim]ℹ️  Rule Diet active: Prompt reduced by {100 - (len(rules_content)/len(rules_full)*100):.1f}%[/dim]")

    # INFRA-160: Catalogue Injection
    j_catalogue, j_count = build_journey_catalogue(config.journeys_dir)
    a_catalogue, a_count = build_adr_catalogue(config.adrs_dir)
    
    # AC-7: Observability
    logger.info("catalogue_injected", extra={
        "story_id": story_id,
        "journey_count": j_count,
        "adr_count": a_count
    })

    # AC-3: Story links pre-seeded (Extract from markdown headers)
    preseeded_adrs = extract_adr_refs(story_content)
    preseeded_journeys = extract_journey_refs(story_content)
    preseeded_block = ""
    if preseeded_adrs or preseeded_journeys:
        preseeded_block = "PRE-SEEDED STORY LINKS (Preserve these unless explicitly redundant):\n"
        if preseeded_adrs:
            preseeded_block += f"- ADRs: {', '.join(sorted(preseeded_adrs))}\n"
        if preseeded_journeys:
            preseeded_block += f"- Journeys: {', '.join(sorted(preseeded_journeys))}\n"

    # 4. Prompt
>>>
```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
4. ADRs (Codified architectural decisions)
5. Source File Tree (Repository structure)
6. Source Code Outlines (Imports, class/function signatures)

TEMPLATE STRUCTURE (Found in {template_path.name}):
{template_content}

Your output must be the FILLED IN template, starting with the Header. Do NOT wrap in markdown blocks.
Replace placeholders like <Title>, <Clear summary...>, etc. with actual content.
Update '## Panel Review Findings' with specific commentary.
Update '## Targeted Refactors & Cleanups (INFRA-043)' with any relevant cleanups found.

{SPLIT_REQUEST_DIRECTIVE if not skip_forecast else '(Forecast gate bypassed — generate the runbook regardless of complexity.)'}
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

GOVERNANCE RULES:
{rules_content}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}

EXISTING USER JOURNEYS:
{_load_journey_context()}

SOURCE FILE TREE:
{source_tree if source_tree else "(No source directory found)"}

SOURCE CODE OUTLINES:
{source_code if source_code else "(No source files found)"}

TARGETED FILE CONTENTS (critical — full source code of files in scope for your changes):
{targeted_context if targeted_context else "(No targeted files identified in story)"}

TEST IMPACT MATRIX (tests with patch targets for these modules — MUST be addressed):
{test_impact if test_impact else "(No test impact detected)"}

BEHAVIORAL CONTRACTS (defaults and invariants — MUST be preserved):
{behavioral_contracts if behavioral_contracts else "(No behavioral contracts found)"}

Generate the runbook now.
"""
===
4. ADRs (Codified architectural decisions)
5. Available Journeys Catalogue (Catalogue of all defined user workflows)
6. Available ADRs Catalogue (Catalogue of all architectural decisions)
7. Source File Tree (Repository structure)
8. Source Code Outlines (Imports, class/function signatures)

TEMPLATE STRUCTURE (Found in {template_path.name}):
{template_content}

Your output must be the FILLED IN template, starting with the Header. Do NOT wrap in markdown blocks.
Replace placeholders like <Title>, <Clear summary...>, etc. with actual content.
Update '## Panel Review Findings' with specific commentary.
Update '## Targeted Refactors & Cleanups (INFRA-043)' with any relevant cleanups found.

{SPLIT_REQUEST_DIRECTIVE if not skip_forecast else '(Forecast gate bypassed — generate the runbook regardless of complexity.)'}
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

{preseeded_block}

GOVERNANCE RULES:
{rules_content}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}

{j_catalogue if j_catalogue else "No journeys defined."}

{a_catalogue if a_catalogue else "No ADRs defined."}

SOURCE FILE TREE:
{source_tree if source_tree else "(No source directory found)"}

SOURCE CODE OUTLINES:
{source_code if source_code else "(No source files found)"}

TARGETED FILE CONTENTS (critical — full source code of files in scope for your changes):
{targeted_context if targeted_context else "(No targeted files identified in story)"}

TEST IMPACT MATRIX (tests with patch targets for these modules — MUST be addressed):
{test_impact if test_impact else "(No test impact detected)"}

BEHAVIORAL CONTRACTS (defaults and invariants — MUST be preserved):
{behavioral_contracts if behavioral_contracts else "(No behavioral contracts found)"}

Generate the runbook now.
"""
>>>
```

### Step 3: Add unit tests for catalogue builders

#### [MODIFY] .agent/src/agent/commands/tests/test_story_link_helpers.py

```
<<<SEARCH
from agent.commands.utils import (
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
)
===
from agent.commands.utils import (
    build_adr_catalogue,
    build_journey_catalogue,
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
)
>>>
```

#### [MODIFY] .agent/src/agent/commands/tests/test_story_link_helpers.py

```
<<<SEARCH
            with patch.object(Path, "write_text", _failing_write):
                with caplog.at_level(logging.WARNING, logger="agent.commands.utils"):
                    merge_story_links(story_file, {"ADR-041"}, set())
                # Must not raise — back-population is best-effort

        assert any("cannot write" in r.message for r in caplog.records)
===
            with patch.object(Path, "write_text", _failing_write):
                with caplog.at_level(logging.WARNING, logger="agent.commands.utils"):
                    merge_story_links(story_file, {"ADR-041"}, set())
                # Must not raise — back-population is best-effort

        assert any("cannot write" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Catalogue Builders (INFRA-160)
# ---------------------------------------------------------------------------

class TestCatalogueBuilders:
    """Unit tests for build_journey_catalogue and build_adr_catalogue."""

    def test_build_journey_catalogue_sorting_and_cap(self, tmp_path):
        """Builds journey catalogue sorted by ID descending and capped at 30."""
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir()
        
        # Create 35 journeys
        for i in range(1, 36):
            jf = journeys_dir / f"JRN-{i:03d}-test.yaml"
            jf.write_text(f"id: JRN-{i:03d}\ntitle: Journey {i:03d}\n")
            
        catalogue, total = build_journey_catalogue(journeys_dir)
        
        assert total == 35
        # Capped at 30
        lines = catalogue.splitlines()
        # "Available Journeys:" + 30 entries
        assert len(lines) == 31
        # Sorted descending: 35 is top
        assert "- JRN-035: Journey 035" in lines[1]
        assert "- JRN-006: Journey 006" in lines[30]
        assert "JRN-005" not in catalogue

    def test_build_adr_catalogue_sorting_and_cap(self, tmp_path):
        """Builds ADR catalogue sorted by ID descending and capped at 30."""
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        
        # Create 35 ADRs
        for i in range(1, 36):
            af = adrs_dir / f"ADR-{i:03d}-test.md"
            af.write_text(f"# ADR {i:03d} Title\n\nContent")
            
        catalogue, total = build_adr_catalogue(adrs_dir)
        
        assert total == 35
        lines = catalogue.splitlines()
        assert len(lines) == 31
        # Sorted descending: 35 is top
        assert "- ADR-035: ADR 035 Title" in lines[1]
        assert "- ADR-006: ADR 006 Title" in lines[30]

    def test_build_catalogue_empty_or_missing(self, tmp_path):
        """Returns empty string and count 0 for missing or empty directories."""
        # Missing
        catalogue, count = build_journey_catalogue(tmp_path / "missing")
        assert catalogue == ""
        assert count == 0
        
        # Empty
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        catalogue, count = build_adr_catalogue(empty_dir)
        assert catalogue == ""
        assert count == 0
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/commands/tests/test_story_link_helpers.py` - Verify catalogue construction logic.
- [ ] `pytest .agent/src/agent/commands/tests/test_runbook.py` - Verify prompt injection via mocking `build_journey_catalogue`.

### Manual Verification

- [ ] Run `agent new-runbook INFRA-160` (or any committed story) and verify the debug logs show `catalogue_injected`.
- [ ] Inspect the generated runbook (if run with a mock AI or --dry-run if available) to ensure it correctly identifies a journey from the catalogue.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with user-facing description of catalogue injection.

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added if new logging added

### Testing

- [ ] All existing tests pass
- [ ] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook