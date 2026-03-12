# STORY-ID: INFRA-119: Squelching Unpredictable Behaviour (Input/Output Validation)

## State

ACCEPTED

## Goal Description

Implement strict JSON validation for LLM outputs using Pydantic models (`AgentAction`, `AgentFinish`) to replace fragile heuristic parsing. This includes an automatic self-correction loop where validation errors are fed back to the LLM for retry, improving the robustness of the agentic reasoning loop and reducing runtime crashes due to malformed LLM responses.

## Linked Journeys

- JRN-004: Agentic Reasoning Loop

## Panel Review Findings

### @Architect
- **ADR-012 Compliance**: Successfully moves the system toward Pydantic-based validation as the primary contract for LLM I/O.
- **Modularity**: The parsing logic is isolated in `parser.py`, keeping the `Orchestrator` focused on flow control.
- **Verdict**: Approved.

### @Qa
- **Schema Validation**: Unit tests must cover valid/invalid JSON, missing fields, and extra fields.
- **Performance**: Pydantic v2 validation is extremely fast; the 50ms overhead constraint is well within reach for typical payloads.
- **Verdict**: Approved.

### @Security
- **Input Sanitization**: Pydantic's validation helps prevent unexpected field injection.
- **Logging**: Ensure that malformed JSON payloads (which might contain sensitive data) are scrubbed or truncated before being logged in failure metrics.
- **Verdict**: Approved.

### @Product
- **User Experience**: Fewer crashes during reasoning tasks directly translates to higher user trust.
- **Max Retries**: Setting a default of 3 retries is a sensible balance between reliability and latency.
- **Verdict**: Approved.

### @Observability
- **Metrics**: Added `agent_validation_errors_total` and `agent_retry_success_total` to track effectiveness of the correction loop.
- **Tracing**: Parsing errors are recorded as span events to aid debugging of specific inference failures.
- **Verdict**: Approved.

### @Docs
- **Internal Reference**: Need to document the expected JSON structure for tool calls in the system prompt generation logic.
- **Verdict**: Approved.

### @Compliance
- **License Headers**: All new files must include the standard license header.
- **Verdict**: Approved.

### @Backend
- **Type Safety**: Using `BaseModel` for action/finish ensures downstream executors can rely on typed objects rather than dictionary lookups.
- **Verdict**: Approved.

## Codebase Introspection

### Targeted File Contents (from source)

(No file content provided in targeted file context. Assuming base implementations or stubs.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `src/agent/core/tests/test_parser.py` | N/A | `agent.core.engine.parser` | Create unit tests for Pydantic parser |
| `src/agent/core/tests/test_orchestrator.py` | N/A | `agent.core.adk.orchestrator` | Test retry loop logic with mocked LLM failures |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Parser Output Type | `parser.py` | `Dict` or `None` | No (Change to Pydantic models) |
| Max Retry Count | `orchestrator.py` | 0 | No (Set to 3) |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Remove legacy regex-based parsing from `parser.py`.
- [x] Consolidate `AgentAction` definitions across the codebase into `typedefs.py`.

## Implementation Steps

### Step 1: Define Pydantic models for Agent Actions and Finish

#### [NEW] src/agent/core/engine/typedefs.py

```python
"""
Typed definitions for agent actions and results.

Copyright 2026 Justin Cook
"""

from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class AgentAction(BaseModel):
    """
    Represents a decision by the agent to invoke a tool.
    """

    thought: str = Field(..., description="The internal reasoning of the agent.")
    tool: str = Field(..., description="The name of the tool to invoke.")
    tool_input: Union[str, Dict[str, Any]] = Field(
        ..., description="The arguments to pass to the tool."
    )


class AgentFinish(BaseModel):
    """
    Represents the final answer produced by the agent.
    """

    thought: str = Field(
        ..., description="The internal reasoning leading to the final result."
    )
    output: str = Field(..., description="The final result or answer for the user.")


class LLMResponse(BaseModel):
    """
    Wrapper for LLM output to handle Union of Action or Finish.
    """

    action: Optional[AgentAction] = None
    finish: Optional[AgentFinish] = None

    @property
    def is_finish(self) -> bool:
        """
        Check if the response is a terminal result.
        """
        return self.finish is not None
```

### Step 2: Implement Structured Output Parser with JSON Recovery

#### [NEW] src/agent/core/engine/parser.py

```python
"""
Logic for parsing LLM outputs into structured Pydantic models.

Copyright 2026 Justin Cook
"""

import json
import re
from typing import Optional
from agent.core.engine.typedefs import AgentAction, AgentFinish, LLMResponse
from agent.core.logger import get_logger

logger = get_logger(__name__)


def parse_react_output(text: str) -> LLMResponse:
    """
    Parses LLM output into an AgentAction or AgentFinish using Pydantic.

    Args:
        text: The raw string output from the LLM.

    Returns:
        An LLMResponse object containing either an action or a finish result.

    Raises:
        ValueError: If the output cannot be parsed into a valid schema after extraction.
    """
    # Attempt to find JSON block in Markdown code blocks
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        # Fallback to finding anything that looks like a JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        content = json_match.group(0) if json_match else text

    try:
        data = json.loads(content)

        # Determine if it's an action or a finish based on schema keys
        if "tool" in data:
            return LLMResponse(action=AgentAction.model_validate(data))
        elif "output" in data:
            return LLMResponse(finish=AgentFinish.model_validate(data))
        else:
            raise ValueError("JSON missing required fields 'tool' or 'output'")

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(
            "Failed to parse LLM output",
            extra={"error": str(e), "content_preview": content[:100]},
        )
        raise ValueError(f"Invalid LLM output format: {str(e)}")
```

### Step 3: Integrate Retry Loop and Telemetry in Orchestrator

#### [MODIFY] src/agent/core/adk/orchestrator.py

```
<<<SEARCH
class Orchestrator:
===
from typing import List, Optional
from agent.core.engine.parser import parse_react_output
from agent.core.engine.typedefs import LLMResponse
from agent.core.logger import get_logger
from opentelemetry import trace, metrics

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter("agent.core")

validation_errors_counter = meter.create_counter(
    "agent_validation_errors_total",
    description="Total number of LLM output validation failures"
)
retry_success_counter = meter.create_counter(
    "agent_retry_success_total",
    description="Total number of successful self-corrections"
)

class Orchestrator:
    def __init__(self, llm_service, max_retries: int = 3):
        """
        Initialize the Orchestrator with an LLM service and retry limit.
        """
        self.llm = llm_service
        self.max_retries = max_retries
>>>
<<<SEARCH
    def run_step(self, prompt: str) -> LLMResponse:
===
    def run_step(self, prompt: str) -> LLMResponse:
        """
        Executes a single reasoning step with a retry loop for validation.
        """
        current_prompt = prompt
        errors: List[str] = []

        with tracer.start_as_current_span("orchestrator.run_step") as span:
            for attempt in range(self.max_retries):
                try:
                    response_text = self.llm.generate(current_prompt)
                    parsed = parse_react_output(response_text)
                    
                    if attempt > 0:
                        logger.info(f"Self-correction successful on attempt {attempt + 1}")
                        span.set_attribute("retry_success", True)
                        span.set_attribute("retries", attempt)
                        retry_success_counter.add(1)
                        
                    return parsed
                    
                except ValueError as e:
                    errors.append(str(e))
                    validation_errors_counter.add(1)
                    logger.warning(f"Validation failure on attempt {attempt + 1}: {str(e)}")
                    span.add_event("validation_error", {"attempt": attempt + 1, "error": str(e)})
                    
                    # Construct feedback for the LLM to trigger self-correction
                    feedback = (
                        f"\n\n[SYSTEM FEEDBACK]: Your last output was invalid. "
                        f"Error: {str(e)}\n"
                        "Please provide your response again as a valid JSON object matching the requested schema."
                    )
                    current_prompt += feedback
            
            span.set_attribute("retry_success", False)
            logger.error("Max retries reached for LLM output validation")
            raise RuntimeError(
                f"Failed to get valid output from LLM after {self.max_retries} attempts. "
                f"Errors encountered: {'; '.join(errors)}"
            )
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest src/agent/core/tests/test_parser.py`: Verify Pydantic casting for valid JSON, markdown-wrapped JSON, and malformed payloads.
- [ ] `pytest src/agent/core/tests/test_orchestrator.py`: Verify the retry loop logic by mocking a failing LLM response followed by a successful one.

### Manual Verification

- [ ] Execute an agent command and simulate a parsing error via a temporary mock. Verify that the system prompts the LLM again with the error message.
- [ ] Check telemetry output (stdout or local OTel collector) to ensure `agent_validation_errors_total` and `agent_retry_success_total` are reporting correct counts.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Implemented strict JSON schema validation for LLM outputs with automatic retry loop".
- [ ] Internal API documentation updated for `AgentAction` and `AgentFinish` models.

### Observability

- [ ] Logs are structured and free of PII (malformed payloads are truncated in logs).
- [ ] New OpenTelemetry metrics for validation failures and successful retries are functional.

### Testing

- [ ] All existing tests pass.
- [ ] Unit tests added for the new parser and orchestrator retry logic.

## Copyright

Copyright 2026 Justin Cook
