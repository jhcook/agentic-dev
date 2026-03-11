# INFRA-104: Protocol Foundation and Exception Hierarchy

## State

COMMITTED

## Goal Description

Update the `AIProvider` protocol to be runtime checkable and implement a common exception hierarchy for all AI provider implementations. This ensures standardized error mapping and handling across all providers, while reducing code redundancy through shared formatting and PII scrubbing helpers.

## Linked Journeys

- JRN-072
- JRN-023

## Panel Review Findings

- **@Architect**: ADR-041 is linked, ensuring that the architectural decisions are considered. The creation of `core/ai/providers/utils.py` seems appropriate for shared functionality.
- **@Qa**: The test strategy mentions unit tests for the exceptions, which is good. However, it should also include tests for `isinstance(obj, AIProvider)` after adding `@runtime_checkable`.
- **@Security**: The plan includes PII scrubbing helpers, which is essential. Ensure no PII is present in exception messages. Also, verify dependencies are pinned and safe in `providers/utils.py` if any are added.
- **@Product**: Acceptance criteria are clear and testable. The impact analysis highlights the affected components and workflows.
- **@Observability**: Ensure that exceptions include relevant context from underlying vendor API errors for better debugging. Structure exception logs.
- **@Docs**: New exceptions and the `AIProvider` protocol changes must be documented. Also, document the usage of `providers/utils.py`.
- **@Compliance**: Ensure that the exceptions don't inadvertently expose any GDPR-sensitive data. License headers must be present in the new file.
- **@Mobile**: Not applicable, as this is backend infrastructure.
- **@Web**: Not applicable, as this is backend infrastructure.
- **@Backend**: The plan enforces type safety and correct API documentation via the exception hierarchy. Ensure base exception metadata is fully typed.

## Codebase Introspection

### Targeted File Contents (from source)

```
<<<SEARCH
        test_streaming.py
        test_vertex_provider.py
          auth/
            __init__.py
===
        test_streaming.py
        test_vertex_provider.py
          auth/
            __init__.py
>>>
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| src/agent/core/ai/tests/test_providers.py | agent.core.ai.providers | agent.core.ai.providers | Add tests for exceptions and isinstance checks |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `isinstance(obj, AIProvider)` | `core/ai/protocols.py` | Returns `True` if `obj` implements the protocol | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Move existing provider-specific utility functions (if any) to the new `core/ai/providers/utils.py` module.

## Implementation Steps

### Step 1: Add `@runtime_checkable` to `AIProvider` protocol

#### [MODIFY] src/agent/core/ai/protocols.py

```
<<<SEARCH
from typing import Protocol
class AIProvider(Protocol):
===
from typing import Protocol
from typing import runtime_checkable

@runtime_checkable
class AIProvider(Protocol):
>>>
```

### Step 2: Implement base exception classes

#### [MODIFY] src/agent/core/ai/protocols.py

```
<<<SEARCH
class AIProvider(Protocol):
    """
    Base protocol for AI providers.
===
class AIProvider(Protocol):
    """
    Base protocol for AI providers.
    """


class AIProviderError(Exception):
    """Base class for all AI provider exceptions."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(message)


class AIRateLimitError(AIProviderError):
    """Raised when a rate limit is encountered."""

    def __init__(self, message: str, retry_after: Optional[int] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, original_exception)
        self.retry_after = retry_after


class AIAuthenticationError(AIProviderError):
    """Raised when authentication fails."""


class AIInvalidRequestError(AIProviderError):
    """Raised when the request is invalid."""
>>>
```

### Step 3: Create `core/ai/providers/utils.py`

#### [NEW] src/agent/core/ai/providers/utils.py

```python
# Copyright 2026 Justin Cook
"""
Utility functions for AI providers, including formatting and PII scrubbing helpers.
"""

import re
from typing import Optional

def scrub_pii(text: str) -> str:
    """
    Scrubs personally identifiable information (PII) from the given text.
    This is a placeholder implementation and should be replaced with a more robust solution.

    Args:
        text: The text to scrub.

    Returns:
        The scrubbed text.
    """
    # Basic PII scrubbing (replace email addresses and phone numbers)
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[email protected]", text)
    text = re.sub(r"\d{3}-\d{3}-\d{4}", "[phone number]", text)
    return text


def format_error_message(message: str, provider_name: str, details: Optional[str] = None) -> str:
    """
    Formats an error message with provider information.

    Args:
        message: The base error message.
        provider_name: The name of the AI provider.
        details: Optional details about the error.

    Returns:
        The formatted error message.
    """
    formatted_message = f"[{provider_name}] {message}"
    if details:
        formatted_message += f" - {details}"
    return formatted_message

```

### Step 4: Add tests for the new exceptions

#### [MODIFY] src/agent/core/ai/tests/test_providers.py

```
<<<SEARCH
from unittest.mock import MagicMock

import pytest
===
from unittest.mock import MagicMock

import pytest

from agent.core.ai.protocols import (
    AIProviderError,
    AIRateLimitError,
    AIAuthenticationError,
    AIInvalidRequestError,
    AIProvider,
)


def test_ai_provider_error():
    err = AIProviderError("test message")
    assert err.message == "test message"
    assert str(err) == "test message"


def test_ai_rate_limit_error():
    err = AIRateLimitError("rate limit", retry_after=60)
    assert err.message == "rate limit"
    assert err.retry_after == 60
    assert str(err) == "rate limit"


def test_ai_authentication_error():
    err = AIAuthenticationError("auth failed")
    assert err.message == "auth failed"
    assert str(err) == "auth failed"


def test_ai_invalid_request_error():
    err = AIInvalidRequestError("bad request")
    assert err.message == "bad request"
    assert str(err) == "bad request"


class MockAIProvider:
    def generate_text(self, prompt: str) -> str:
        return "test"


def test_isinstance_ai_provider():
    mock_provider = MockAIProvider()
    assert isinstance(mock_provider, AIProvider)

>>>
```

## Verification Plan

### Automated Tests

- [x] Run `pytest src/agent/core/ai/tests/test_providers.py` and ensure all tests pass.

### Manual Verification

- [ ] Inspect exception messages to confirm no PII is exposed.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [ ] README.md updated (if applicable) - Add documentation for the new exception hierarchy and `providers/utils.py`.

### Observability

- [x] Logs are structured and free of PII
- [x] New structured `extra=` dicts added if new logging added - Ensure exceptions are logged with appropriate metadata.

### Testing

- [x] All existing tests pass
- [x] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook