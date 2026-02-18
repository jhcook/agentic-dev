# INFRA-063: AI-Powered Journey Test Generation

## State

ACCEPTED

## Goal Description

Implement an `--ai` flag for the `agent journey backfill-tests` command to automatically generate test implementations using the AI service, significantly reducing the manual effort required to create regression tests for user journeys.

## Linked Journeys

- JRN-053: Journey Test Coverage

## Panel Review Findings

**@Architect**:

- ADR-005 (AI-Driven Governance Preflight) and ADR-025 (Lazy Initialization) are correctly linked.
- Refactoring `backfill_tests` into `_iter_eligible_journeys()`, `_generate_stub()`, `_generate_ai_test()` helpers is sound.
- This is the first time the agent generates *executable code* (vs. markdown/JSON). `ast.parse()` is the minimum safety gate.
- Keep all AI prompt logic centralized in `prompts.py`.

**@QA**:

- Test Strategy is comprehensive with 12 automated tests covering normal, edge, and failure paths.
- Edge cases: missing `implementation.files`, 0-step journeys, AI returning valid Python with no assertions.
- Test idempotency: running `--ai` twice should skip existing files (AC-6).

**@Security**:

- Source context must be scrubbed via `scrub_sensitive_data()` before inclusion in prompts (AC-5).
- Validate `implementation.files` paths remain within repo root using path containment.
- No `exec()` or `eval()` on AI output — `ast.parse()` for validation only.
- `.agent/src/` exception: `subprocess`, `os`, `shutil` are permitted per security instructions.

**@Product**:

- ACs are clear and testable. Interactive confirm UX (AC-4) ensures human review without wasted AI calls.
- `--journey JRN-XXX` targeting is a good UX addition (AC-7).
- `--write` for CI batch mode and `--dry-run` for preview-only are intuitive flag semantics.
- Progress bar for 50+ journeys provides necessary feedback (AC-12).

**@Observability**:

- Structured logging per AI call: `journey_id`, `scope`, `token_count`, `duration_s`, `status`.
- Summary metric at end: total processed, AI successes, fallbacks, skips, errors.

**@Docs**:

- Update `commands.md` with `--ai`, `--write`, `--journey` flags.
- Update CHANGELOG.
- Differentiate AI-generated docstrings from stubs.

**@Compliance**:

- SOC 2 CC7.1: interactive confirm default (not auto-writing) ensures compliance.
- Apache 2.0 license header mandatory in generated test files (AC-10).
- No PII/credentials in AI prompts — `scrub_sensitive_data()` enforced.

**@Mobile** / **@Web**:

- Phase 1 scoped to pytest only. Framework-specific generation deferred.
- `implementation.framework` field prepared for future use.

**@Backend**:

- Lazy init of AI service per ADR-025 — import inside function body.
- `ast.parse()` validation before writing. Never `exec()`/`eval()`.
- Full type hints on all new helpers.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract stub generation from `backfill_tests` into `_generate_stub()` helper
- [ ] Convert `console.print()` to `logger` for structured output in new functions
- [ ] Add type hints to all new functions

## Implementation Steps

### Phase 0: Pre-Validation

1. Verify INFRA-058 `backfill_tests` command works (`agent journey backfill-tests --dry-run`)
2. Verify `scrub_sensitive_data()` import path: `from agent.core.security import scrub_sensitive_data`
3. Verify AI service lazy import pattern: `from agent.core.ai.service import AIService`

---

### Phase 1: Refactor `backfill_tests` into Helpers

#### [MODIFY] [journey.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/journey.py)

Extract existing logic into testable helpers without changing behavior.

**1a. Add `_iter_eligible_journeys()` generator** (extract from lines 459-477):

```python
def _iter_eligible_journeys(
    journeys_dir: Path,
    scope: Optional[str] = None,
    journey_id: Optional[str] = None,
) -> Generator[Tuple[Path, dict], None, None]:
    """Yields (yaml_path, parsed_data) for COMMITTED journeys without tests."""
    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        if scope and scope_dir.name.upper() != scope.upper():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            jid = data.get("id", jfile.stem)
            if journey_id and jid != journey_id:
                continue
            j_state = (data.get("state") or "DRAFT").upper()
            tests = data.get("implementation", {}).get("tests", [])
            if j_state != "COMMITTED" or tests:
                continue
            yield jfile, data
```

**1b. Add `_generate_stub()` function** (extract from lines 493-520):

```python
def _generate_stub(data: dict, jid: str) -> str:
    """Generate a pytest stub from journey assertions."""
    slug = jid.lower().replace("-", "_")
    steps = data.get("steps", [])
    test_funcs: List[str] = []
    for i, step in enumerate(steps, 1):
        assertions = step.get("assertions", []) if isinstance(step, dict) else []
        assertion_comments = (
            "\n".join(f"    # {a}" for a in assertions)
            if assertions else "    # No assertions defined"
        )
        action_str = (
            step.get("action", "unnamed")[:60]
            if isinstance(step, dict) else "unnamed"
        )
        test_funcs.append(
            f'\n@pytest.mark.journey("{jid}")\n'
            f"def test_{slug}_step_{i}():\n"
            f'    """Step {i}: {action_str}"""\n'
            f"{assertion_comments}\n"
            '    pytest.skip("Not yet implemented")\n'
        )
    return (
        f'"""Auto-generated test stubs for {jid}."""\n'
        "import pytest\n"
        + "".join(test_funcs)
    )
```

**1c. Refactor `backfill_tests` to use helpers** — replace inline logic with calls to `_iter_eligible_journeys()` and `_generate_stub()`. Verify existing behavior unchanged.

---

### Phase 2: Add AI Test Generation

#### [MODIFY] [journey.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/journey.py)

**2a. Add new CLI flags to `backfill_tests`:**

```python
@app.command("backfill-tests")
def backfill_tests(
    scope: Optional[str] = typer.Option(None, "--scope", help="Filter by scope."),
    journey_id: Optional[str] = typer.Option(None, "--journey", help="Target single journey (JRN-XXX)."),
    ai: bool = typer.Option(False, "--ai", help="Generate tests with AI. Previews and prompts before writing."),
    write: bool = typer.Option(False, "--write", help="Batch-write all without prompts (CI mode)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, no prompts, no writes."),
) -> None:
```

**2b. Add `_generate_ai_test()` function:**

```python
_LICENSE_HEADER = '''\
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 ...
'''

_MAX_SOURCE_CHARS = 32_000  # ~8k tokens

def _generate_ai_test(
    data: dict, jid: str, repo_root: Path
) -> Optional[str]:
    """Generate a pytest test using the AI service.

    Returns generated test code on success, None on failure (caller falls back to stub).
    """
    import time
    from agent.core.ai.service import AIService  # Lazy init (ADR-025)
    from agent.core.security import scrub_sensitive_data

    start = time.monotonic()
    steps = data.get("steps", [])
    if not steps:
        logger.warning("journey=%s | No steps defined, skipping AI generation", jid)
        return None

    # Build source context from implementation.files
    impl_files = data.get("implementation", {}).get("files", [])
    source_context = ""
    for rel_path in impl_files:
        fpath = repo_root / rel_path
        if not fpath.is_file():
            logger.warning("journey=%s | Source file not found: %s", jid, rel_path)
            continue
        if not str(fpath.resolve()).startswith(str(repo_root.resolve())):
            logger.warning("journey=%s | Path escapes repo root: %s", jid, rel_path)
            continue
        try:
            raw = fpath.read_text(errors="replace")[:20_000]
            scrubbed = scrub_sensitive_data(raw)
            source_context += f"\n--- {rel_path} ---\n{scrubbed}"
        except Exception:
            logger.warning("journey=%s | Error reading %s", jid, rel_path, exc_info=True)

    # Truncate to token budget
    if len(source_context) > _MAX_SOURCE_CHARS:
        source_context = source_context[:_MAX_SOURCE_CHARS]

    # Build prompt
    from agent.core.ai.prompts import generate_test_prompt
    prompt = generate_test_prompt(data, jid, source_context)

    # Call AI service
    try:
        service = AIService.get_service()
        response = service.generate(prompt)
    except Exception:
        logger.exception("journey=%s | AI service call failed", jid)
        return None

    # Validate generated code
    try:
        ast.parse(response)
    except SyntaxError as e:
        logger.warning("journey=%s | AI output has syntax error: %s", jid, e)
        return None

    duration = time.monotonic() - start
    logger.info(
        "journey=%s | scope=%s | token_count=%d | duration_s=%.1f | status=success",
        jid, data.get("scope", "UNKNOWN"), len(source_context), duration,
    )

    slug = jid.lower().replace("-", "_")
    return (
        _LICENSE_HEADER
        + f'"""AI-generated regression tests for {jid}."""\n'
        + response
    )
```

**2c. Update `backfill_tests` main loop:**

- If `--ai` is set, call `_generate_ai_test()` first
- On success, use AI-generated code; on `None`, fall back to `_generate_stub()`
- If `--ai` (default): preview in Rich `Syntax` panel, prompt `Write to {path}? [y/N/all/skip]`
  - `y` → write this file, `N` → skip, `all` → write remaining without prompting, `skip` → stop processing
- If `--ai --write`: batch-write all generated files without prompts (CI mode)
- If `--ai --dry-run`: preview all to stdout, no prompts, no writes
- Add Rich progress bar wrapping the journey iteration loop
- Emit summary metrics at end

---

### Phase 3: Add AI Prompt

#### [MODIFY] [prompts.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/ai/prompts.py)

Add `generate_test_prompt()` alongside existing prompt generators:

```python
def generate_test_prompt(data: dict, jid: str, source_context: str) -> str:
    """Generate a prompt for AI to write pytest test code from a journey."""
    steps = data.get("steps", [])
    steps_text = "\n".join(
        f"  {i}. {s.get('action', 'unnamed')}"
        + (("\n     Assertions: " + ", ".join(s.get("assertions", []))) if s.get("assertions") else "")
        for i, s in enumerate(steps, 1)
        if isinstance(s, dict)
    )
    slug = jid.lower().replace("-", "_")

    return f"""You are an expert Python test engineer.
Write a complete pytest test module for user journey {jid}.

JOURNEY STEPS:
{steps_text}

SOURCE CODE CONTEXT:
{source_context}

REQUIREMENTS:
- Use pytest framework only (no unittest, no selenium).
- Include `import pytest` at the top.
- Add `@pytest.mark.journey("{jid}")` decorator on each test function.
- Name test functions as `test_{slug}_step_N`.
- Write real assertions (not `pytest.skip`).
- Mock external dependencies as needed.
- Output ONLY valid Python code, no markdown fences.
"""
```

---

### Phase 4: Unit Tests

#### [NEW] [test_journey_ai.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/tests/commands/test_journey_ai.py)

Tests organized by AC:

| # | Test | AC |
|---|------|----|
| 1 | AI returns valid code → file written when `--write` | AC-1 |
| 2 | AI returns `SyntaxError` code → fallback to stub | AC-9, Neg |
| 3 | `--ai` without `--write` → stdout only, no file | AC-4 |
| 4 | `--scope INFRA` filters correctly | AC-7 |
| 5 | `--journey JRN-053` targets single journey | AC-7 |
| 6 | Source context truncated at budget | AC-5 |
| 7 | `scrub_sensitive_data()` called on source | AC-5 |
| 8 | Missing `implementation.files` path → warning, continue | Edge |
| 9 | Journey with 0 steps → skip AI, use stub | Edge |
| 10 | Generated file has license header | AC-10 |
| 11 | AI service unavailable → fallback to stub | AC-8 |
| 12 | Generated file has AI docstring | AC-10 |

## Verification Plan

### Automated Tests

```bash
# Run all journey AI tests
pytest .agent/src/agent/tests/commands/test_journey_ai.py -v

# Verify no regressions in existing journey tests
pytest .agent/src/agent/tests/commands/ -k journey -v
```

### Manual Verification

1. `agent journey backfill-tests --ai` → verify dry-run output to stdout
2. `agent journey backfill-tests --ai --write --journey JRN-053` → verify file created
3. `python -c "import ast; ast.parse(open('tests/journeys/test_jrn_053.py').read())"` → syntax ok
4. Verify progress bar renders correctly with 5+ journeys
5. Verify structured log output contains expected fields

## Definition of Done

### Documentation

- [ ] `commands.md` updated with `--ai`, `--write`, `--journey` flags
- [ ] CHANGELOG.md entry added
- [ ] AI-generated test docstrings differentiate from stubs

### Observability

- [ ] Logs are structured and free of PII
- [ ] Per-journey log: `journey_id`, `scope`, `token_count`, `duration_s`, `status`
- [ ] Summary: total processed, AI successes, fallbacks, skips, errors

### Testing

- [ ] Unit tests passed (12 tests)
- [ ] Integration test: `--ai --dry-run` with real journey
- [ ] No regressions in existing `backfill-tests` behavior
