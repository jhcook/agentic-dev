# INFRA-072: Create `agent review-voice` CLI Command

## State

ACCEPTED

## Goal Description

Create a new `agent review-voice` CLI command that fetches the last voice agent session via `fetch_last_session.py`, sends it to AI for analysis (latency, accuracy, tone, interruption), and outputs structured UX feedback. This replaces the fully-manual `/review-voice` workflow.

## Linked Journeys

- JRN-061: Voice Session Review Workflow

## Panel Review Findings

- **@Architect**: New `voice.py` module under `agent/commands/` follows existing command patterns. Register on main `app` via `app.command("review-voice")`. Use subprocess for `fetch_last_session.py` — keeps voice infra decoupled from CLI internals.
- **@QA**: 4 unit tests required per story. Mock subprocess for script execution and AI service for analysis. Use sample session fixture with realistic conversation data.
- **@Security**: Subprocess call uses hardcoded script path — no injection risk. Scrub session content with `scrub_sensitive_data()` before AI submission. No PII should persist in logs; only log session size and duration.
- **@Product**: AC1-AC5 cover the full workflow lifecycle. Structured output with per-category ratings makes feedback actionable.
- **@Observability**: Log session size (chars), analysis duration, and AI provider used.
- **@Compliance**: Session data may contain user utterances (PII). Document GDPR lawful basis in docstring: Art. 6(1)(f) legitimate interest for UX improvement. Scrub before AI submission.

## Implementation Steps

### 1. Create `voice.py` Command Module

#### [NEW] .agent/src/agent/commands/voice.py

- Apache 2.0 license header (required by NFR)
- `review_voice()` function with:
  - `--provider` flag for AI provider selection
  - `--json` flag for structured JSON output (CI mode)
- Logic:
  1. Locate `fetch_last_session.py` in `.agent/scripts/`; error clearly if missing
  2. Run via `subprocess.run(["python3", script_path], capture_output=True)`
  3. If stdout is empty or stderr indicates no session → print clean message, exit 0
  4. Scrub session content via `scrub_sensitive_data()`
  5. Build AI prompt evaluating: latency, accuracy, tone, interruption
  6. Call `ai_service.complete()` (lazy init per ADR-025)
  7. Parse/display structured output with per-category ratings
  8. Log session size and analysis duration

### 2. Register Command in `main.py`

#### [MODIFY] .agent/src/agent/main.py

- Import `voice` from `agent.commands`
- Register: `app.command(name="review-voice")(voice.review_voice)`

### 3. Simplify `/review-voice` Workflow

#### [MODIFY] .agent/workflows/review-voice.md

- Replace 25-line manual process with CLI-first instructions:

  ```
  1. Run `agent review-voice`
  2. Review the structured UX feedback
  ```

### 4. Add Unit Tests

#### [NEW] .agent/tests/commands/test_voice.py

- `test_session_fetch_subprocess` — verifies subprocess call to `fetch_last_session.py`
- `test_ai_prompt_includes_session` — verifies AI prompt contains session content
- `test_structured_output_categories` — verifies output has latency/accuracy/tone/interruption ratings
- `test_missing_script_error` — verifies clean error when `fetch_last_session.py` absent

## Files

| File | Action | Description |
|------|--------|-------------|
| `.agent/src/agent/commands/voice.py` | NEW | `review-voice` command module |
| `.agent/src/agent/main.py` | MODIFY | Register `review-voice` command |
| `.agent/workflows/review-voice.md` | MODIFY | Simplify to CLI-first |
| `.agent/tests/commands/test_voice.py` | NEW | 4 unit tests |
| `CHANGELOG.md` | MODIFY | Add INFRA-072 entry |

## Verification Plan

### Automated Tests

- [ ] `test_session_fetch_subprocess` passes
- [ ] `test_ai_prompt_includes_session` passes
- [ ] `test_structured_output_categories` passes
- [ ] `test_missing_script_error` passes
- [ ] Existing tests unaffected

### Manual Verification

- [ ] `agent review-voice --help` shows correct usage
- [ ] `agent review-voice` with no voice infra reports cleanly
