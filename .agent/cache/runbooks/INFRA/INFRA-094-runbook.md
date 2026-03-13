# INFRA-094: SPLIT_REQUEST Fallback for Runbook Generation

## State

COMMITTED

## Goal Description

Implement a SPLIT_REQUEST fallback mechanism within the runbook generation pipeline. When the AI Governance Panel generates a runbook that exceeds complexity thresholds, the AI itself will emit a structured `SPLIT_REQUEST` JSON block instead of a normal runbook. The CLI will detect this response, parse the decomposition suggestions, save them to `.agent/cache/split_requests/{story_id}.json`, and exit with code 2.

This is **Layer 2a** of the INFRA-089 defence-in-depth strategy — a secondary defence that catches discrepancies between the heuristic forecast (Layer 1, INFRA-093) and the actual AI-generated plan.

## Linked Journeys

- JRN-064: Forecast-Gated Story Decomposition (error path: SPLIT_REQUEST)

## Panel Review Findings

### @Architect
- **ADR Compliance**: Follows ADR-005 (AI-Driven Governance Preflight) by adding a fail-fast mechanism at the AI response stage. The Forecast Gate (INFRA-093) is Layer 1 (heuristic). This adds Layer 2a (AI-aware).
- **Design Scope**: All changes are confined to `runbook.py` — no new modules needed. The prompt directive is injected into the existing system prompt, and response parsing happens after `ai_service.complete()` returns. This respects the single-module boundary.
- **JSON Contract**: The `SPLIT_REQUEST` JSON schema must be documented inline in the prompt to ensure the AI emits a parseable, deterministic structure. Recommend a minimal schema: `{"SPLIT_REQUEST": true, "reason": str, "suggestions": [str]}`.
- **Robustness**: AI responses are non-deterministic. The parser MUST handle: (1) valid JSON, (2) JSON embedded in surrounding markdown, (3) malformed JSON → graceful fallback (treat as normal runbook). This avoids false-positive blocking.

### @QA
- **Test Strategy**: The story defines three unit test cases (SPLIT_REQUEST parsed, normal response proceeds, malformed fallback). These are sufficient. Recommend adding a fourth: SPLIT_REQUEST JSON embedded in markdown fences (common AI pattern).
- **Exit Codes**: Exit code 2 must be tested explicitly — this is critical for CI/CD pipeline integration and matches the Forecast Gate's exit code convention.
- **Negative Path**: Verify that a normal runbook response (no SPLIT_REQUEST marker) proceeds to file write without any change in behavior.

### @Security
- **Prompt Injection**: The SPLIT_REQUEST directive is part of the *system* prompt only. It does not accept user input that could alter the directive. Risk is low.
- **Data Privacy**: The `split_requests/{story_id}.json` file stores decomposition *suggestions* (strings), not story content. However, the `reason` field could echo parts of the story. Ensure `scrub_sensitive_data()` is applied to the reason field before saving.
- **Audit Logging**: SPLIT_REQUEST events must be logged with structured data (`story_id`, `reason`, `suggestion_count`) per NFR. No PII in logs — only metadata.

### @Product
- **UX**: When a SPLIT_REQUEST is detected, the CLI should print a clear, actionable message: "⚠️ AI recommends splitting this story" with the saved file path and a pointer to next steps (run `agent new-story` for each suggestion).
- **Acceptance Criteria**: All 5 ACs from the story are addressed:
  - AC-1: Prompt directive added → Implementation Step 1
  - AC-2: JSON parse logic → Implementation Step 2
  - AC-3: Save to `split_requests/` → Implementation Step 3
  - AC-4: Exit code 2 → Implementation Step 4
  - Negative: Normal flow proceeds → Implementation Step 2 (else branch)

### @Observability
- **Structured Logging**: Log the SPLIT_REQUEST event with `story_id`, `reason` (truncated to 200 chars), and `suggestion_count`. Use existing `logger.warning()` pattern for consistency with Forecast Gate logging.
- **Tracing**: No new OpenTelemetry span needed — the SPLIT_REQUEST check occurs within the existing `new_runbook` function flow, which is already traced at the command level.

### @Docs
- **CHANGELOG**: Add INFRA-094 entry under "Added" section.
- **CLI Help**: No new CLI flags — this is a transparent backend behaviour. No docs change needed beyond CHANGELOG.

### @Compliance
- **SOC2**: The structured log for SPLIT_REQUEST events satisfies the audit trail requirement. No user bypass flag is needed — this is an AI-initiated decomposition.
- **Licensing**: New test file must include Apache 2.0 header. The `split_requests/` JSON files are cache artifacts, not source — no header needed.

### @Mobile
- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Web
- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Backend
- **Type Safety**: Use `json.loads()` with explicit `try/except json.JSONDecodeError`. The parsed result should be validated against expected keys before saving.
- **Pattern**: Follow the existing pattern in `runbook.py` where `ai_service.complete()` returns a string that is then processed. The SPLIT_REQUEST check is a simple string search + JSON parse — no architectural change.
- **Config Path**: Add `split_requests_dir` property to `Config.__init__` following the existing `plans_dir` / `runbooks_dir` pattern: `self.split_requests_dir = self.cache_dir / "split_requests"`.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract the SPLIT_REQUEST JSON schema constant to a module-level `SPLIT_REQUEST_SCHEMA_HINT` string for readability.

## Implementation Steps

### Config

#### [MODIFY] src/agent/core/config.py

- Add `split_requests_dir` path after the existing `plans_dir` line:

    ```python
    self.plans_dir = self.cache_dir / "plans"
    self.split_requests_dir = self.cache_dir / "split_requests"
    self.runbooks_dir = self.cache_dir / "runbooks"
    ```

### CLI / Commands

#### [MODIFY] src/agent/commands/runbook.py

**Step 0 — Module-Level Import**

- Add `import json` to the module-level imports (stdlib — not a lazy import per ADR-025):

    ```python
    import json
    import re
    ```

**Step 1 — AC-1: Complexity Gatekeeper Prompt Directive**

- Add a `SPLIT_REQUEST_DIRECTIVE` constant at module level (after the existing imports). Include a brief comment for maintainability:

    ```python
    # Complexity Gatekeeper directive injected into the runbook system prompt (INFRA-094)
    SPLIT_REQUEST_DIRECTIVE = """
    COMPLEXITY GATEKEEPER DIRECTIVE:
    If, during runbook generation, you determine that the implementation plan would exceed
    ANY of these thresholds:
    - More than 400 lines of code changed
    - More than 8 implementation steps
    - More than 4 files modified

    Then you MUST NOT generate a runbook. Instead, emit ONLY the following JSON block:

    ```json
    {
      "SPLIT_REQUEST": true,
      "reason": "<one-sentence explanation of why the story is too complex>",
      "suggestions": [
        "<child story 1 title and scope>",
        "<child story 2 title and scope>"
      ]
    }
    ```

    Do NOT wrap this in any other text or markdown if you determine the story must be split.
    If the story fits within the thresholds, proceed with normal runbook generation.
    """

    ```

- Inject this directive into the `system_prompt` in the `new_runbook()` function, appending it after the existing template instructions (before the closing `"""`):

    ```python
    system_prompt = f"""You are the AI Governance Panel...
    ...
    {SPLIT_REQUEST_DIRECTIVE}
    """
    ```

**Step 2 — AC-2: SPLIT_REQUEST Response Detection and Parse**

- After `content = ai_service.complete(system_prompt, user_prompt)` and the empty check, add SPLIT_REQUEST detection logic:

    ```python
    # -- SPLIT_REQUEST Fallback (INFRA-094) --
    if content and "SPLIT_REQUEST" in content:
        split_data = _parse_split_request(content)
        if split_data:
            # AC-3: Save decomposition suggestions
            config.split_requests_dir.mkdir(parents=True, exist_ok=True)
            split_path = config.split_requests_dir / f"{story_id}.json"
            split_path.write_text(json.dumps(split_data, indent=2))

            # NFR: Structured logging (SOC2)
            logger.warning(
                "split_request story=%s reason=%s suggestion_count=%d",
                story_id,
                scrub_sensitive_data(split_data.get("reason", ""))[:200],
                len(split_data.get("suggestions", [])),
            )

            # AC-4: Exit with code 2 and guidance
            console.print("[bold yellow]⚠️  AI recommends splitting this story.[/bold yellow]")
            console.print(f"  • Reason: {split_data.get('reason', 'N/A')}")
            console.print(f"  • Suggestions: {len(split_data.get('suggestions', []))}")
            for i, s in enumerate(split_data.get("suggestions", []), 1):
                console.print(f"    {i}. {s}")
            console.print(f"\nDecomposition saved to: {split_path}")
            console.print("[dim]Create child stories with: agent new-story <ID>[/dim]")
            raise typer.Exit(code=2)
    ```

- If `"SPLIT_REQUEST"` is NOT in `content`, proceed with existing file write (no change — the negative AC is satisfied by this else-branch).

**Step 3 — Add `_parse_split_request()` helper function**

- Add a new function after `_load_journey_context()`:

    ```python
    def _parse_split_request(content: str) -> Optional[dict]:
        """Extract and parse SPLIT_REQUEST JSON from AI response.

        Handles:
        - Pure JSON response
        - JSON embedded in markdown code fences
        - Malformed JSON (returns None → treat as normal runbook)

        Args:
            content: Raw AI response string.

        Returns:
            Parsed dict if valid SPLIT_REQUEST, None otherwise.
        """
        # Try direct parse first
        try:
            data = json.loads(content.strip())
            if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        # Try extracting from markdown code fences (\n made optional for AI variance)
        json_match = re.search(r"```(?:json)?\s*\n?(.+?)\n?\s*```", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1).strip())
                if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

        # Malformed or not a SPLIT_REQUEST — graceful fallback
        logger.debug("SPLIT_REQUEST marker found but JSON parse failed, treating as normal runbook")
        return None
    ```

## Verification Plan

### Automated Tests

#### [NEW] .agent/tests/commands/test_runbook_split_request.py

> **Fixture Note**: The `mock_fs` fixture MUST mock `config.cache_dir` to `tmp_path / "cache"` and `config.split_requests_dir` to `tmp_path / "cache" / "split_requests"` to prevent filesystem leakage into the real cache directory.

- **Test 1: Valid SPLIT_REQUEST parsed and saved** — Mock `ai_service.complete` to return valid SPLIT_REQUEST JSON. Assert:
  - `_parse_split_request` returns a dict with `SPLIT_REQUEST: true`
  - `config.split_requests_dir / f"{story_id}.json"` file exists and contains the parsed data
  - CLI exits with code 2
  - Guidance message printed to stdout

- **Test 2: Normal runbook proceeds** — Mock `ai_service.complete` to return a normal runbook string (no SPLIT_REQUEST marker). Assert:
  - `_parse_split_request` is not called (or `"SPLIT_REQUEST" not in content` short-circuits)
  - Runbook file is written to `runbooks/` directory
  - CLI exits with code 0

- **Test 3: Malformed SPLIT_REQUEST JSON → graceful fallback** — Mock response containing `"SPLIT_REQUEST"` string but invalid JSON. Assert:
  - `_parse_split_request` returns `None`
  - Runbook file exists at `runbooks/{scope}/{story_id}-runbook.md` with the malformed content written as-is
  - CLI exits with code 0 (not code 2)
  - No crash

- **Test 4: SPLIT_REQUEST embedded in markdown fences** — Mock response with JSON inside ` ```json ... ``` ` fences. Assert:
  - `_parse_split_request` correctly extracts and parses the JSON
  - Exit code 2

- **Test 5: Structured logging emitted** — Verify `logger.warning` is called with `split_request`, `story_id`, `reason`, and `suggestion_count`.

- [ ] `pytest .agent/tests/commands/test_runbook_split_request.py`

### Manual Verification

- [ ] Run `agent new-runbook <STORY_ID>` on a story known to produce a complex runbook and verify the SPLIT_REQUEST fallback triggers (may need to temporarily lower thresholds or craft a test story).
- [ ] Verify `.agent/cache/split_requests/` directory is created and contains a valid JSON file.
- [ ] Verify `agent.log` contains the structured `split_request` log entry with `story_id`, `reason`, and `suggestion_count`.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-094 entry.
- [ ] README.md updated (if applicable) — likely N/A for internal CLI enhancement.
- [ ] API Documentation updated (if applicable) — N/A.

### Observability

- [ ] Logs are structured and free of PII (reason field scrubbed via `scrub_sensitive_data`).
- [ ] Split request events logged with `story_id`, `reason`, `suggestion_count`.

### Testing

- [ ] Unit tests passed (`test_runbook_split_request.py`).
- [ ] Existing runbook tests still pass (`test_runbook.py`, `test_runbook_forecast.py`, `test_runbook_prompt.py`).

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
