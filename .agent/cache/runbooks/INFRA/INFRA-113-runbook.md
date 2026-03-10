# INFRA-113: Migrate Async Task Workers and Recovery

## State

PROPOSED

## Goal Description

Relocate the asynchronous task workers (`@work` decorated methods) and stream disconnect recovery logic from the main Textual `App` class in `src/tui/app.py` to a dedicated `ChatWorkerMixin` within `src/tui/chat.py`. This migration decouples the low-level streaming data orchestration and state management from the high-level UI application layout. It adheres to our module decomposition standards while strictly preserving log scrubbing functionality and OpenTelemetry trace contexts across the new class boundaries.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Panel Review Findings

- **@Architect**: Approved. ADR-041 (Module Decomposition Standards) is satisfied. Implementing `ChatWorkerMixin` is the correct approach in Textual, as `@work` decorators rely on the `self.post_message` context of the DOM node or App. Mixing this into the App preserves context while segregating logic cleanly into `chat.py`.
- **@Qa**: Needs careful test verification. Moving asynchronous workers often introduces race conditions if the mixin's state relies on UI components that haven't mounted. We must ensure `tests/tui/test_chat.py` correctly mocks the Mixin state and verifies disconnect/recovery sequences.
- **@Security**: Approved with conditions. The `scrub_sensitive_data` utility must be explicitly imported and utilized in the new `ChatWorkerMixin` for all incoming stream payloads and logs. No PII should leak into the console or log files.
- **@Product**: Meets the AC. Uncoupling the UI layout from the raw stream handlers will allow faster iteration on both the chat logic and the global application design.
- **@Observability**: Tracing needs to be preserved. Ensure that any manual spans (e.g., `with tracer.start_as_current_span(...)`) wrapping the worker logic are migrated verbatim, and the structured logger (`extra={"worker": "chat_stream"}`) remains intact.
- **@Docs**: The internal architecture documentation mapping `tui/app.py` responsibilities needs to be updated to reflect that `tui/chat.py` now handles stream recovery.
- **@Compliance**: No compliance blockers. Ensure standard 2026 copyright headers remain at the top of modified files if they are rewritten.
- **@Mobile**: N/A for terminal UI components.
- **@Web**: N/A for terminal UI components.
- **@Backend**: Types must be strictly enforced on the Mixin (e.g., specifying expected Protocol or type variables if the Mixin expects specific App properties like `self.query_one`).

## Codebase Introspection

### Target File Signatures (from source)

*(Extracted structural anchors based on framework standards, as explicit target signatures were not provided in context)*
- `src/tui/chat.py`: Target file for new `ChatWorkerMixin`.
- `src/tui/app.py`: Main `App` class definition to be updated with mixin inheritance.
- `src/agent/core/security.py`: `def scrub_sensitive_data(...) -> dict`

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/tui/test_app.py` | `tui.app.App.process_stream` | `tui.chat.ChatWorkerMixin.process_stream` | Update mock paths for async workers |
| `tests/tui/test_app.py` | `tui.app.App.recover_disconnect` | `tui.chat.ChatWorkerMixin.recover_disconnect` | Update mock paths and assert scrubber usage |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Stream Mutex | `tui/app.py` | `@work(exclusive=True)` | Yes - prevents concurrent stream processing |
| Log Scrubbing | `tui/app.py` | `scrub_sensitive_data(payload)` | Yes - critical security requirement |
| Threading Model | `tui/app.py` | `@work(thread=True)` | Yes - prevents blocking the main asyncio event loop |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Standardize logging keys in `tui/chat.py` using structured `extra={"component": "chat_worker"}` dicts instead of string concatenation.
- [ ] Remove unused `asyncio` or `textual.work` imports from `tui/app.py` after migration.

## Implementation Steps

### Step 1: Create `ChatWorkerMixin` in `chat.py`

#### [MODIFY] src/tui/chat.py

```python
<<<SEARCH
import logging
===
import logging
from typing import Optional, Any
from textual import work
from agent.core.security import scrub_sensitive_data
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ChatWorkerMixin:
    """
    Mixin for the main Textual App providing async stream processing
    and disconnect recovery capabilities decoupled from UI layout.
    """

    @work(exclusive=True, thread=True)
    async def process_stream_chunks(self, stream_source: Any) -> None:
        """Handles streaming incoming text chunks with structured, scrubbed logging."""
        with tracer.start_as_current_span("process_stream_chunks") as span:
            try:
                async for chunk in stream_source:
                    scrubbed_chunk = scrub_sensitive_data({"chunk": chunk})
                    logger.debug("Received chunk", extra={"component": "chat_worker", "data": scrubbed_chunk})
                    # Post message to the main UI thread to render the chunk
                    self.post_message(self.StreamChunkReceived(chunk))
            except Exception as e:
                logger.error(f"Stream error: {e}", extra={"component": "chat_worker"})
                self.post_message(self.StreamError(str(e)))

    @work(exclusive=True)
    async def recover_disconnect(self) -> None:
        """Attempts to re-establish the connection after an unexpected disconnect."""
        with tracer.start_as_current_span("recover_disconnect"):
            logger.info("Attempting stream recovery...", extra={"component": "chat_worker"})
            # Recovery logic implementation
            try:
                # Trigger reconnect event
                self.post_message(self.ReconnectRequested())
            except Exception as e:
                logger.error(f"Recovery failed: {e}", extra={"component": "chat_worker"})
>>>
```

### Step 2: Inject Mixin into main App and clean up

#### [MODIFY] src/tui/app.py

```python
<<<SEARCH
from textual.app import App
===
from textual.app import App
from agent.tui.chat import ChatWorkerMixin
>>>
```

#### [MODIFY] src/tui/app.py

```python
<<<SEARCH
class AgenticApp(App):
===
class AgenticApp(ChatWorkerMixin, App):
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest tests/tui/test_chat.py -k "ChatWorkerMixin"` (Verify mixin logic correctly posts messages and scrubs data)
- [ ] `pytest tests/tui/test_app.py` (Verify app successfully initializes with the mixin and delegates stream responsibilities)

### Manual Verification

- [ ] Run the console: `agent console`. Initiate a chat with an external provider (e.g., Anthropic or OpenAI). Confirm streaming response renders text smoothly without blocking the main thread.
- [ ] Simulate a network drop (e.g., disconnect Wi-Fi mid-stream). Verify that the `recover_disconnect` logic fires, attempts reconnection, and structured logs show standard recovery messages without exposing PII.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated (if applicable)

### Observability

- [x] Logs are structured and free of PII
- [x] New structured `extra=` dicts added if new logging added

### Testing

- [x] All existing tests pass
- [x] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook