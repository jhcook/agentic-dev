# INFRA-060: Panel Verdict Anchoring

## State

ACCEPTED

## Goal Description

Enforce explicit citation of relevant ADRs and journeys by the governance panel during code review. Add reference extraction, filesystem validation, and audit logging so panel verdicts are anchored to the project's first-class governance objects.

## Linked Journeys

- JRN-045: Governance Hardening — Exception Records

## Panel Review Findings

**@Architect**:

- PASS. `AVAILABLE REFERENCES:` ID list built inside `convene_council_full()` (centralized, not in callers). Extract ADR/EXC IDs from `adrs_content` via regex, scan `config.journeys_dir` for JRN IDs. Function signature unchanged. `_extract_references()` and `_validate_references()` placed in `governance.py` alongside `_parse_findings()`.
- `_load_adrs()` already injects full summaries via `<adrs>` tag — new line injects **IDs only** (one compact line). No prompt bloat.

**@QA**:

- PASS. Consultative mode gap identified — `_parse_findings()` never called in `mode == "consultative"` (line 417-418). `_extract_references()` must run separately on raw AI output. Multi-chunk deduplication (AC-13) prevents repeated citations. SUPERSEDED ADR info notes (AC-14). Tests for consultative mode and SUPERSEDED ADRs.
- `_parse_findings()` remains backward-compatible when `REFERENCES:` section is absent — defaults to empty list.

**@Security**:

- PASS. Hallucination detection via filesystem validation — catches AI-fabricated ADR IDs. `AVAILABLE REFERENCES:` list derived from filesystem directory listings (`config.adrs_dir.glob()`, `config.journeys_dir.rglob()`), not user input. `ADR-\d+` regex constrains glob patterns — no path traversal risk. `scrub_sensitive_data()` already applied to AI output.

**@Product**:

- PASS. Non-blocking warnings for missing/invalid refs — deterministic enforcement stays in INFRA-057. Reference Summary Table (AC-16) after all role panels gives developers a single verification point. INFRA-059 graceful degradation (AC-6) prevents hard failures.

**@Observability**:

- PASS. Per-role span attributes (`role_name`, `ref_count`, `valid_count`, `invalid_count`). Aggregate metrics after role loop: `panel.total_refs`, `panel.citation_rate`, `panel.hallucination_rate`. Citation rate as prompt-quality adoption metric.

**@Compliance**:

- PASS. Audit log `## Reference Validation` section appended before file write (line 487). Full `valid_refs`/`invalid_refs` lists for SOC 2 CC7.1. Traceability chain: `Code Change → Diff → AI Review → Citation → Validation`.

**@Backend**:

- PASS. Dual extraction strategy: parse `REFERENCES:` section if present AND scan full text with regex as fallback. `_validate_references()` handles `EXC-` patterns in same `adrs_dir`. `config.journeys_dir` already exists at line 52 of `config.py`.

**@Docs**:

- PASS. CHANGELOG entry for reference validation. Prompt format documentation update.

**@Mobile** / **@Web**: No concerns — backend/CLI only.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Add type hints to all new public functions
- [ ] Ensure consistent Rich console formatting for reference output

## Implementation Steps

### Step 1: Update system prompt in `convene_council_full()` [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Add `REFERENCES:` section to the gatekeeper output format at line 399-403:

```diff
                         "Output format (use EXACTLY this structure):\n"
                         "VERDICT: [PASS|BLOCK]\n"
                         "SUMMARY: <one line summary>\n"
                         "FINDINGS:\n- <finding 1>\n- <finding 2>\n"
+                        "REFERENCES:\n- ADR-NNN: <reason>\n- JRN-NNN: <reason>\n"
                         "REQUIRED_CHANGES:\n- <change 1>\n(Only if BLOCK)"
```

### Step 2: Inject `AVAILABLE REFERENCES:` compact ID line [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Inside `convene_council_full()`, **before** the role loop (after line 343), build the ID list from existing parameters:

```python
# Build compact reference ID list (AC-2)
# Extract ADR/EXC IDs from adrs_content (already passed as parameter)
_available_ids = sorted(set(re.findall(r'\b(ADR-\d+|EXC-\d+)\b', adrs_content)))

# Scan journeys_dir for JRN IDs
if config.journeys_dir.exists():
    for _scope in config.journeys_dir.iterdir():
        if _scope.is_dir():
            for _jf in _scope.glob("JRN-*.yaml"):
                _available_ids.append(_jf.stem.split("-", 1)[0] + "-" + _jf.stem.split("-", 1)[1].split("-")[0] if "-" in _jf.stem else _jf.stem)
    # Better: extract JRN-NNN from filename
    _jrn_ids = sorted(set(
        re.match(r'(JRN-\d+)', f.stem).group(1)
        for _scope in config.journeys_dir.iterdir() if _scope.is_dir()
        for f in _scope.glob("JRN-*.yaml")
        if re.match(r'(JRN-\d+)', f.stem)
    ))
    _available_ids.extend(_jrn_ids)

_available_refs_line = f"AVAILABLE REFERENCES: {', '.join(sorted(set(_available_ids)))}"
```

Append `_available_refs_line` to the `user_prompt` at line 407-412, after the `<adrs>` tag:

```diff
             user_prompt = f"<story>{story_content}</story>\n<rules>{rules_content}</rules>\n"
             if adrs_content:
                 user_prompt += f"<adrs>{adrs_content}</adrs>\n"
+            user_prompt += f"{_available_refs_line}\n"
             if instructions_content:
                 user_prompt += f"<instructions>{instructions_content}</instructions>\n"
```

### Step 3: Add `_extract_references()` function [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Add after `_parse_bullet_list()` (after line 184):

```python
def _extract_references(text: str) -> List[str]:
    """Extract ADR, JRN, and EXC reference IDs from text using regex.

    Dual strategy: scan full text for reference patterns.
    Returns deduplicated, sorted list.
    """
    refs = set(re.findall(r'\b(ADR-\d+|JRN-\d+|EXC-\d+)\b', text))
    return sorted(refs)
```

### Step 4: Add `_validate_references()` function [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Add after `_extract_references()`:

```python
def _validate_references(
    refs: List[str],
    adrs_dir: Path,
    journeys_dir: Path,
) -> Tuple[List[str], List[str]]:
    """Validate references against filesystem.

    ADR-NNN and EXC-NNN: check adrs_dir for ADR-NNN*.md / EXC-NNN*.md
    JRN-NNN: check journeys_dir (recursive) for JRN-NNN*.yaml

    Returns (valid_refs, invalid_refs).
    """
    valid, invalid = [], []
    for ref in refs:
        prefix = ref.split("-")[0]
        if prefix in ("ADR", "EXC"):
            matches = list(adrs_dir.glob(f"{ref}*.md")) if adrs_dir.exists() else []
        elif prefix == "JRN":
            matches = list(journeys_dir.rglob(f"{ref}*.yaml")) if journeys_dir.exists() else []
        else:
            matches = []
        if matches:
            valid.append(ref)
        else:
            invalid.append(ref)
    return valid, invalid
```

### Step 5: Extend `_parse_findings()` with `references` field [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

At line 135, add `"references": []` to the default result dict. Then after the `REQUIRED_CHANGES` extraction (line 166), add:

```python
    # Extract REFERENCES section (AC-3 formal path)
    refs_match = re.search(
        r"^REFERENCES:\s*\n(.*?)(?:^REQUIRED_CHANGES:|^FINDINGS:|^VERDICT:|^SUMMARY:|\Z)",
        review,
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    # Also scan full text as fallback (AC-3 dual strategy)
    result["references"] = _extract_references(review)
```

This ensures backward compatibility — if `REFERENCES:` is absent, the full-text scan still picks up any inline citations, and if no refs exist, the list defaults to empty.

### Step 6: Integrate reference extraction/validation into `convene_council_full()` [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

After the AI response is received (inside the chunk loop, lines 414-434), add reference extraction for **both** modes:

```python
                # --- Reference Extraction (INFRA-060) ---
                # Always extract references, regardless of mode (AC-11)
                chunk_refs = _extract_references(review)

                if mode == "consultative":
                    role_findings.append(review)
                else:
                    parsed = _parse_findings(review)
                    # ... existing verdict/summary/findings logic ...
                    chunk_refs = parsed.get("references", chunk_refs)
```

After the chunk loop (line 438), accumulate and deduplicate per-role references:

```python
        # Deduplicate references across chunks (AC-13)
        role_refs = sorted(set(all_role_refs))

        # Validate references (AC-4)
        valid_refs, invalid_refs = _validate_references(
            role_refs, config.adrs_dir, config.journeys_dir
        )

        role_data["references"] = {
            "cited": role_refs,
            "valid": valid_refs,
            "invalid": invalid_refs,
        }

        # Emit warnings for invalid/missing references (AC-7, AC-8)
        for inv in invalid_refs:
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} cited {inv} which does not exist")

        if not role_refs:
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} — no references provided")

        # Check for SUPERSEDED ADRs (AC-14)
        for ref in valid_refs:
            if ref.startswith("ADR-") or ref.startswith("EXC-"):
                try:
                    adr_files = list(config.adrs_dir.glob(f"{ref}*.md"))
                    if adr_files:
                        content = adr_files[0].read_text()
                        if re.search(r'(?i)\bSUPERSEDED\b', content):
                            if progress_callback:
                                progress_callback(
                                    f"ℹ️ {ref} is SUPERSEDED — consider citing its replacement"
                                )
                except Exception:
                    pass
```

### Step 7: Append `## Reference Validation` to audit log [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Before the audit log write at line 487, append the reference validation section:

```python
    # Reference Validation section (AC-9)
    # Traceability: Code Change → Diff → AI Review → Citation → Validation
    report += "\n## Reference Validation\n\n"
    report += "_Traceability: Code Change → Diff → AI Review → Citation → Validation_\n\n"
    for rd in json_roles:
        refs = rd.get("references", {})
        report += f"### @{rd['name']}\n"
        report += f"**Cited**: {', '.join(refs.get('cited', [])) or 'None'}\n"
        report += f"**Valid**: {', '.join(refs.get('valid', [])) or 'None'}\n"
        report += f"**Invalid**: {', '.join(refs.get('invalid', [])) or 'None'}\n\n"
```

### Step 8: Add Reference Summary Table to `check.py` preflight output [MODIFY]

#### [MODIFY] [check.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/check.py)

After the panel role loop in `preflight()` (where `json_report` is populated), add:

```python
    # Reference Summary Table (AC-16)
    all_ref_data = {}  # ref_id -> {status, cited_by}
    for rd in json_report.get("json_report", {}).get("roles", []):
        refs = rd.get("references", {})
        for ref in refs.get("cited", []):
            if ref not in all_ref_data:
                all_ref_data[ref] = {"valid": ref in refs.get("valid", []), "cited_by": []}
            all_ref_data[ref]["cited_by"].append(rd["name"])

    if all_ref_data:
        from rich.table import Table
        ref_table = Table(title="Reference Summary", show_lines=True)
        ref_table.add_column("Reference", style="cyan")
        ref_table.add_column("Status")
        ref_table.add_column("Cited By")
        for ref_id, data in sorted(all_ref_data.items()):
            status = "[green]Valid[/green]" if data["valid"] else "[yellow]Invalid[/yellow]"
            ref_table.add_row(ref_id, status, ", ".join(data["cited_by"]))
        console.print(ref_table)
```

### Step 9: Add INFRA-059 completeness check to `preflight()` [MODIFY]

#### [MODIFY] [check.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/check.py)

After the Reference Summary Table (AC-6):

```python
    # Completeness check: did the panel consider relevant ADRs? (AC-6)
    try:
        from agent.db.journey_index import get_affected_journeys, is_stale
        # ... get affected journeys from INFRA-059 impact map ...
        # Compare affected journey ADRs against panel citations
        # Emit warning for uncited relevant ADRs
    except ImportError:
        console.print("[dim]ℹ️ Journey impact map not available — skipping completeness check[/dim]")
```

### Step 10: Add OTel span attributes [MODIFY]

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

After the role loop (line 479), add aggregate span attributes:

```python
    # OTel reference metrics (AC-10)
    total_refs = sum(len(rd.get("references", {}).get("cited", [])) for rd in json_roles)
    roles_with_refs = sum(1 for rd in json_roles if rd.get("references", {}).get("cited"))
    total_invalid = sum(len(rd.get("references", {}).get("invalid", [])) for rd in json_roles)

    json_report["ref_metrics"] = {
        "total_refs": total_refs,
        "citation_rate": roles_with_refs / len(json_roles) if json_roles else 0,
        "hallucination_rate": total_invalid / total_refs if total_refs > 0 else 0,
    }
```

### Step 11: Create unit tests [NEW]

#### [NEW] [test_reference_validation.py](file:///Users/jcook/repo/agentic-dev/.agent/tests/core/test_reference_validation.py)

Unit tests covering:

- `test_extract_references()` — regex extracts ADR-025, JRN-012, EXC-001 from mixed text
- `test_extract_references_dedup()` — same ADR cited 3x returns single entry
- `test_extract_references_malformed_ignored()` — `ADR25` (no hyphen) not extracted
- `test_validate_references_valid()` — ADR-025 exists on disk → valid
- `test_validate_references_invalid()` — ADR-099 doesn't exist → invalid
- `test_validate_references_exc()` — EXC-001 exists in `adrs_dir` → valid
- `test_validate_references_mixed()` — mix of valid and invalid
- `test_parse_findings_with_references()` — AI output with REFERENCES section parsed
- `test_parse_findings_no_references()` — backward-compatible, empty list
- `test_consultative_mode_reference_extraction()` — raw output yields references
- `test_superseded_adr_reference()` — SUPERSEDED ADR produces info note
- `test_available_references_line_construction()` — IDs from adrs_content + journeys_dir

### Step 12: Create integration tests [NEW]

#### [NEW] [test_panel_references.py](file:///Users/jcook/repo/agentic-dev/.agent/tests/commands/test_panel_references.py)

- `test_panel_includes_references()` — `env -u VIRTUAL_ENV uv run agent panel` output includes per-role references
- `test_preflight_reference_summary_table()` — preflight outputs Reference Summary Table
- `test_invalid_reference_warning()` — invalid ref emits WARNING, not BLOCK

## Verification Plan

### Automated Tests

- [ ] `uv run pytest tests/core/test_reference_validation.py` — 12 unit tests pass
- [ ] `uv run pytest tests/commands/test_panel_references.py` — 3 integration tests pass
- [ ] `uv run pytest tests/` — full regression, no failures introduced

### Manual Verification

- [ ] `env -u VIRTUAL_ENV uv run agent panel INFRA-060` outputs per-role references and Reference Summary Table
- [ ] `env -u VIRTUAL_ENV uv run agent preflight --story INFRA-060` emits reference validation warnings
- [ ] Panel in consultative mode still extracts references from raw output
- [ ] Citing non-existent ADR-999 produces WARNING, not BLOCK
- [ ] Changeset touching no ADR-governed files — no citation warnings emitted
- [ ] SUPERSEDED ADR citation produces ℹ️ info note

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with reference validation feature
- [ ] Prompt format documentation updated

### Observability

- [ ] Structured logs free of PII
- [ ] `ref_metrics` in JSON report with `total_refs`, `citation_rate`, `hallucination_rate`

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed
- [ ] Existing tests unbroken

## Rollback Plan

- Remove `_extract_references()`, `_validate_references()` from `governance.py`.
- Revert prompt template changes (remove REFERENCES requirement and AVAILABLE REFERENCES line).
- Remove Reference Summary Table from `check.py`.
- Panel returns to unanchored verdicts — all changes are additive, no regression risk.
