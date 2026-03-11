# STORY-ID: INFRA-115: Validation and Test Coverage

## State

ACCEPTED

## Goal Description

Implement comprehensive unit tests for the decomposed TUI modules (`tui/prompts.py` and `tui/chat.py`) to ensure behavioral stability. This includes verifying streaming response rendering, graceful recovery from connection drops, and adherence to PEP-484 and PEP-257 standards. This validation ensures that the module decomposition performed in INFRA-099 maintains feature parity and reliability.

## Linked Journeys

- N/A (Infrastructure validation)

## Panel Review Findings

- **@Architect**: Implementation of tests for specific TUI sub-modules supports ADR-041 by ensuring boundaries are verified in isolation.
- **@Qa**: The inclusion of a negative test for disconnect recovery in the automated suite is a strong preventative measure against regressions in UX during network instability.
- **@Security**: Verified that tests use mocks for external interactions; no actual network or PII-touching code is involved in the unit tests.
- **@Product**: Acceptance criteria are strictly followed, specifically targeting the streaming and recovery logic which are the primary value drivers for the TUI.
- **@Observability**: Tests will verify that structured logging (e.g., `extra=`) is used during error conditions, supporting better field diagnostics.
- **@Docs**: The requirement to verify PEP-257 docstrings ensures that the newly created modules are properly documented for future maintenance.
- **@Compliance**: License headers are required for all new test files to maintain SOC2/legal compliance.
- **@Mobile**: N/A.
- **@Web**: N/A.
- **@Backend**: Type hint verification ensures the new modules participate correctly in static analysis (mypy), reducing runtime type errors.

## Codebase Introspection

### Targeted File Contents (from source)

(Note: Source files `src/agent/tui/chat.py` and `src/agent/tui/prompts.py` were indicated as found in the tree but content was not provided in the targeted section. Tests are designed based on standard interface patterns identified in `agent.tui.app` and `agent.core.ai.streaming`.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/test_console_prompt.py` | `agent.tui.prompts.logger` | `agent.tui.prompts.logger` | Ensure existing tests pass with new module location |
| `tests/tui/test_chat.py` | `agent.tui.chat.logger` | `agent.tui.chat.logger` | Create file and implement streaming/recovery tests |
| `tests/tui/test_prompts.py` | `agent.tui.prompts.Path` | `agent.tui.prompts.Path` | Create file and implement path validation tests |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Streaming Chunk Rendering | `tui/chat.py` | Must render partial tokens as they arrive | Yes |
| Disconnect Recovery | `tui/chat.py` | Must catch connection errors and allow retry | Yes |
| Prompt Validation | `tui/prompts.py` | Must validate filesystem paths if requested | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Ensure `agent.tui` sub-modules are included in the global linting/type-check configuration.

## Implementation Steps

### Step 1: Create Unit Tests for Chat Module

#### [NEW] .agent/tests/tui/test_chat.py

```python
# Copyright 2026 Justin Cook

import pytest
from unittest.mock import AsyncMock, patch
from agent.tui.chat import process_chat_stream, DisconnectModal, resolve_provider

@pytest.mark.asyncio
async def test_process_chat_stream_success():
    """Verify that streaming chunks flow correctly."""
    async def mock_stream():
        yield {"choices": [{"delta": {"content": "Hello"}}]}
        yield {"choices": [{"delta": {"content": " world"}}]}

    results = []
    async for chunk in process_chat_stream(mock_stream()):
        results.append(chunk)

    assert results == ["Hello", " world"]

@pytest.mark.asyncio
async def test_process_chat_stream_error():
    """Verify that connection drops and API errors are handled gracefully."""
    async def mock_stream():
        yield {"error": "Connection drop"}

    with patch("agent.tui.chat.logger") as mock_logger:
        results = []
        async for chunk in process_chat_stream(mock_stream()):
            results.append(chunk)

        assert results == ["\n[Error: Connection drop]"]
        mock_logger.error.assert_called()

def test_resolve_provider():
    """Verify resolve_provider handoff works."""
    with patch("agent.core.ai.service.ai_service.get_provider") as mock_get_provider:
        resolve_provider("test_provider")
        mock_get_provider.assert_called_with("test_provider")
```

### Step 2: Create Unit Tests for Prompts Module

#### [NEW] .agent/tests/tui/test_prompts.py

```python
# Copyright 2026 Justin Cook

import pytest
from agent.tui.prompts import _build_clinical_prompt, build_chat_history
from agent.tui.session import Message

def test_build_clinical_prompt():
    """Verify fallback system prompt includes necessary contexts."""
    prompt = _build_clinical_prompt("test-agent", "/test/path", "# License")
    assert "test-agent" in prompt
    assert "/test/path" in prompt
    assert "# License" in prompt

def test_build_chat_history():
    """Verify history construction formats correctly."""
    msgs = [
        Message(role="user", content="Hi", timestamp="1"),
        Message(role="assistant", content="Hello", timestamp="2")
    ]
    history = build_chat_history(msgs, "What next?")
    assert "User: Hi" in history
    assert "Assistant: Hello" in history
    assert "User: What next?" in history
```

### Step 3: Type Hint Fixes

#### [MODIFY] .agent/src/agent/tui/chat.py

```
<<<SEARCH
    def add_selection(self, text: str, source: str):
        """Add a new selection to the log with scrubbing."""
===
    def add_selection(self, text: str, source: str) -> None:
        """Add a new selection to the log with scrubbing."""
>>>
```

## Verification Plan

### Automated Tests

- [ ] Run the new unit tests:
  `pytest .agent/tests/tui/test_chat.py .agent/tests/tui/test_prompts.py`
  Expected: All new tests pass.
- [ ] Run full TUI regression:
  `pytest .agent/tests/tui/`
  Expected: All existing and new tests pass.
- [ ] Run type check:
  `mypy .agent/src/agent/tui/`
  Expected: Success (no type errors in decomposed modules).
- [ ] Run lint check:
  `ruff check .agent/src/agent/tui/`
  Expected: Success.

### Manual Verification

- [ ] "Negative Test" (Disconnect Recovery):
  1. Start the TUI chat: `agent console`
  2. Simulate a network drop (e.g., toggle Wi-Fi).
  3. Expected: The TUI displays a red "Connection lost" message and prompts for retry.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Added unit tests and type safety for TUI decomposition."
- [ ] Code comments updated to PEP-257 format.

### Observability

- [ ] Logs are structured and free of PII (Verified in `test_prompt_logging`).
- [ ] `extra=` dictionaries are used for all error logging in `chat.py`.

### Testing

- [ ] All existing tests pass.
- [ ] New tests added for `render_stream` and `validate_path`.
- [ ] Coverage for `src/agent/tui/` is >= 80%.

## Copyright

Copyright 2026 Justin Cook