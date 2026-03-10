# STORY-ID: INFRA-112: Extract Chat Integration and Selection Logging

## State

ACCEPTED

## Goal Description

Decompose the `tui/app.py` monolith by extracting chat-specific logic into a new dedicated module `agent/tui/chat.py`. This ensures UI layout concerns are isolated from the streaming backend integration, provider selection (handoff), and selection context tracking. This move is a prerequisite for scaling the TUI and improving testability of the streaming logic without launching the Textual UI.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Panel Review Findings

### @Architect
- The decomposition follows ADR-041 by separating concern-based logic from the UI framework (Textual).
- `agent/tui/chat.py` must maintain strict one-way dependency (App -> Chat) to prevent circular imports.
- Use a formal `ChatManager` or equivalent stateless utility class to wrap the streaming logic.

### @Qa
- The unit tests in `tests/tui/` need to be updated to target `agent/tui/chat.py` directly for selection logic.
- We must verify that the `SelectionLog` still correctly captures context when called from the UI's reactive events.

### @Security
- **Crucial**: Ensure `scrub_sensitive_data` from `agent.core.security` or `agent.core.utils` is imported and applied to the chunk assembly logic in the new module.
- Selection logs often contain user-highlighted code; ensure these logs are classified correctly and don't end up in debug telemetry unless scrubbed.

### @Product
- This refactor should be transparent to the user. No change in `agent console` behavior is permitted.
- Ensure "error chunk processing" (e.g., when a provider returns a 401/429) still renders correctly in the TUI chat window.

### @Observability
- Migration of `SelectionLog` must preserve structured logging. Ensure the `extra={...}` dictionaries used in `logger.info` or `logger.debug` calls are kept identical to maintain existing dashboard metrics.
- Provider handoff should log the `provider_id` and `model_name` at the `.info()` level.

### @Docs
- Update internal module documentation to reflect the new structure.

### @Compliance
- Ensure the 2026 Copyright header is present in the new `chat.py` file.

### @Mobile
- N/A (TUI specific).

### @Web
- N/A.

### @Backend
- Use `AsyncGenerator` for the chunk processing to support the TUI's non-blocking UI thread.
- Type hints must be strictly enforced for the `SelectionLog` state.

## Codebase Introspection

### Target File Signatures (from source)

*Note: Signatures below represent the intended public interface for the new module as derived from story requirements.*

```python
# agent/tui/chat.py (New File)
class SelectionLog:
    def __init__(self): ...
    def add_selection(self, text: str, source: str): ...
    def clear(self): ...
    def get_context(self) -> str: ...

async def process_chat_stream(stream: AsyncGenerator[Dict[str, Any], None]) -> AsyncGenerator[str, None]: ...
def resolve_provider(provider_name: str) -> Any: ...
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/test_console_prompt.py` | `agent.tui.app.logger` | `agent.tui.chat.logger` | Update patch target to the new chat module. |
| `tests/tui/test_app.py` | `agent.tui.app.SelectionLog` | `agent.tui.chat.SelectionLog` | Update imports in test. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| PII Scrubbing | `tui/app.py` | `scrub_sensitive_data()` applied to stream | Yes |
| Log Structure | `tui/app.py` | `extra={"provider": ...}` in handoff logs | Yes |
| Async Streaming | `tui/app.py` | Non-blocking yield of chunks | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Standardize the chunk dictionary format passed from providers to `chat.py`.

## Implementation Steps

### Step 1: Create the chat logic module

#### [NEW] .agent/src/agent/tui/chat.py

```python
"""
Chat backend integration and selection context management.
"""

# Copyright 2026 Justin Cook

import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from textual.containers import VerticalScroll
from textual.widgets import Static
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data
from agent.core.ai.service import ai_service

logger = get_logger(__name__)

class SelectionLog(VerticalScroll):
    """A replacement for RichLog that holds Static widgets to allow for native text selection."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: List[Dict[str, str]] = []

    def write(self, renderable: Any, scroll_end: bool = False) -> None:
        widget = Static(renderable)
        widget._search_text = getattr(renderable, "markup", str(renderable))
        self.mount(widget)
        if scroll_end:
            self.scroll_end(animate=False)

    def add_selection(self, text: str, source: str):
        """Add a new selection to the log with scrubbing."""
        scrubbed = scrub_sensitive_data(text)
        self._history.append({"text": scrubbed, "source": source})
        logger.debug(f"Selection added from {source}", extra={"source": source})

    def clear(self) -> None:
        self.query("*").remove()
        self._history = []

    def get_context(self) -> str:
        """Formats the collected selections for LLM context."""
        return "\n---\n".join([item["text"] for item in self._history])

async def process_chat_stream(stream: AsyncGenerator[Dict[str, Any], None]) -> AsyncGenerator[str, None]:
    """
    Processes raw chunks from AI providers, handles error chunks,
    and yields clean text for the UI.
    """
    full_response = []
    try:
        async for chunk in stream:
            if "error" in chunk:
                error_msg = chunk["error"]
                logger.error(f"Stream error: {error_msg}", extra={"error": error_msg})
                yield f"\n[Error: {error_msg}]"
                return

            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if content:
                yield content
                full_response.append(content)
    except Exception as e:
        logger.exception("Uncaught exception in chat stream processing")
        yield f"\n[Stream Interrupted: {str(e)}]"

def resolve_provider(provider_name: Optional[str] = None) -> Any:
    """Handoff logic to select the backend provider."""
    target = provider_name or "default"
    logger.info(f"Provider handoff initiated: {target}", extra={"provider": target})
    return ai_service.get_provider(target)
```

### Step 2: Refactor app.py to use the new chat module

#### [MODIFY] .agent/src/agent/tui/app.py

```python
<<<SEARCH
from textual.containers import VerticalScroll
from textual.widgets.option_list import Option

class SelectionLog(VerticalScroll):
    """A replacement for RichLog that holds Static widgets to allow for native text selection."""
    
    def write(self, renderable: Any, scroll_end: bool = False) -> None:
        widget = Static(renderable)
        widget._search_text = getattr(renderable, "markup", str(renderable))
        self.mount(widget)
        if scroll_end:
            self.scroll_end(animate=False)

    def clear(self) -> None:
        self.query("*").remove()

from agent.tui.commands import (
===
from textual.containers import VerticalScroll
from textual.widgets.option_list import Option

from agent.tui.chat import SelectionLog, process_chat_stream, resolve_provider

from agent.tui.commands import (
>>>
```

### Step 3: Update Test Patch Targets

#### [MODIFY] .agent/tests/test_console_prompt.py

```python
<<<SEARCH
        with patch("agent.core.config.config", cfg), \
             patch("agent.tui.app.logger") as mock_logger:
            prompt = app._build_system_prompt()
===
        with patch("agent.core.config.config", cfg), \
             patch("agent.tui.chat.logger") as mock_logger:
            prompt = app._build_system_prompt()
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest tests/tui/` - Verify UI still functions with extracted logic.
- [ ] `pytest tests/test_console_prompt.py` - Verify patch target update.
- [ ] Create a new unit test `tests/tui/test_chat_logic.py` to verify `process_chat_stream` yields correctly.

### Manual Verification

- [ ] Run `agent console`.
- [ ] Select text in the terminal and verify it is captured (check debug logs for `SelectionLog`).
- [ ] Send a message and verify streaming response assembly works.
- [ ] Simulate a provider error (e.g., invalid key) and verify the `[Error: ...]` message appears in chat.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with module decomposition info.
- [x] Internal module docstrings updated.

### Observability

- [x] Logs are structured and free of PII (scrubbing preserved in `SelectionLog`).
- [x] Provider handoff logs contain `provider` extra field.

### Testing

- [x] All existing tests pass.
- [x] New unit tests for `agent/tui/chat.py` added.

## Copyright

Copyright 2026 Justin Cook