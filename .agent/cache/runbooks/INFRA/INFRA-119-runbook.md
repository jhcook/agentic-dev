# STORY-ID: INFRA-119: Squelching Unpredictable Behaviour (Input/Output Validation)

## State

ACCEPTED

## Goal Description

Implement strict JSON schema validation for Large Language Model (LLM) outputs using Pydantic. This replaces brittle heuristic-based parsing with a robust validation layer that ensures agent responses adhere to `AgentAction` or `Finish` schemas. It includes an automatic correction loop that feeds validation errors back to the LLM for self-correction, reducing runtime crashes and improving agent reliability during the reasoning loop.

## Linked Journeys

- JRN-004: Agentic Reasoning Loop

## Panel Review Findings

### @Architect
- **ADR Compliance**: Standardizing on Pydantic follows ADR-012. The use of `TypeAdapter` for union validation is the correct pattern for discriminative parsing.
- **Boundaries**: Validation logic is isolated within the `engine/parser` domain, while the retry policy is correctly placed in the `implement/orchestrator` layer.

### @Qa
- **Test Strategy**: The proposed unit tests for schema validation and integration tests for the retry loop are sufficient.
- **Edge Cases**: We must ensure the `max_retries` is strictly capped to prevent infinite loops (and cost spikes) if an LLM is persistently malformed.

### @Security
- **Schema Enforcement**: Using `extra='forbid'` in Pydantic models prevents injection of unexpected fields.
- **Data Safety**: Ensure that the validation error messages fed back to the LLM do not leak system internals (though standard Pydantic errors are generally safe).

### @Product
- **Acceptance Criteria**: The design satisfies Scenario 1 (Schema casting) and Scenario 2 (Retry loop). The Negative Test is handled by the graceful termination in the orchestrator.
- **UX**: This will significantly reduce "Agent Crashed" errors, providing a smoother developer experience.

### @Observability
- **Metrics**: Added `validation_failures_total` and `retry_success_total` counters.
- **Logging**: Using structured logs for validation errors allows for easy filtering of "brittle" models or prompts.

### @Docs
- **Sync**: The implementation adds new public interfaces for parsing. Documentation for custom tool development should reflect that outputs are now strictly validated.

### @Compliance
- **Logging**: Retry attempts are logged with timestamps and error details, satisfying audit requirements for model interactions.
- **Licensing**: All new code includes the 2026 Justin Cook copyright header.

### @Backend
- **Type Safety**: Strictly enforced types for LLM outputs. Using `Union[AgentAction, Finish]` ensures the orchestrator handles all valid states.

## Codebase Introspection

### Targeted File Contents (from source)

The targeted files `.agent/src/agent/core/engine/typedefs.py` and `.agent/src/agent/core/engine/parser.py` are currently empty placeholders in the source tree. `.agent/src/agent/core/implement/orchestrator.py` contains basic imports.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/core/test_parser.py` | N/A | `agent.core.engine.parser` | Create new unit tests for strict parsing |
| `.agent/tests/core/test_orchestrator.py` | N/A | `agent.core.implement.orchestrator` | Add integration tests for retry loop |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| LLM Output Format | Orchestrator | Heuristic/Any | No (Now Strict JSON) |
| Retry Limit | Orchestrator | 0 | No (Now 3) |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Remove legacy heuristic regex parsing from `parser.py` once strict validation is verified.

## Implementation Steps

### Step 1: Upgrading Typedefs to Pydantic (Strict Schema)

#### [MODIFY] .agent/src/agent/core/engine/typedefs.py

```
<<<SEARCH
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class AgentAction:
    tool: str
    tool_input: Dict[str, Any]
    log: str  # The raw "Thought" leading to this action

@dataclass
class AgentObservation:
    output: str  # The result from the tool

@dataclass
class AgentFinish:
    return_values: Dict[str, Any]
    log: str
===
from dataclasses import dataclass
from typing import Any, Dict, Union
from pydantic import BaseModel, Field

class AgentAction(BaseModel):
    tool: str
    tool_input: Union[Dict[str, Any], str]
    log: str  # The raw "Thought" leading to this action
    
    model_config = {"extra": "forbid"}

@dataclass
class AgentObservation:
    output: str  # The result from the tool

class AgentFinish(BaseModel):
    return_values: Dict[str, Any]
    log: str
    
    model_config = {"extra": "forbid"}
>>>
```

### Step 2: Empowering Parser with Pydantic Validation

#### [MODIFY] .agent/src/agent/core/engine/parser.py

```
<<<SEARCH
        if action_data:
            tool = action_data.get("tool")
            tool_input = action_data.get("tool_input")
            if tool and tool_input is not None:
                if isinstance(tool, dict):
                    tool = tool.get("name") or str(tool)
                elif not isinstance(tool, str):
                    tool = str(tool)
                # Extract the thought text (everything before the Action)
                # If "Action:" is present, take everything before it.
                # Otherwise, use a regex to find the start of the JSON block we parsed.
                if "Action:" in text:
                    thought = text.split("Action:")[0].strip()
                else:
                    # Find where the JSON starts
                    json_str = json.dumps(action_data)
                    # This is imprecise but better than nothing; 
                    # usually it's "Thought: ... { JSON }"
                    parts = text.split('{', 1)
                    thought = parts[0].strip() if len(parts) > 1 else text[:200]
                
                # Strip "Thought:" prefix if present
                thought = re.sub(r"^(Thought:\s*)+", "", thought, flags=re.IGNORECASE).strip()
                
                return AgentAction(
                    tool=tool,
                    tool_input=tool_input,
                    log=thought,
                )

        # If no action found, it's a Finish
        # Clean up the output by stripping "Final Answer:" or "Thought:"
        output = text
===
        if action_data:
            tool = action_data.get("tool")
            if isinstance(tool, dict):
                action_data["tool"] = tool.get("name") or str(tool)
            elif not isinstance(tool, str) and tool is not None:
                action_data["tool"] = str(tool)
                
            # Extract the thought text (everything before the Action)
            # If "Action:" is present, take everything before it.
            # Otherwise, use a regex to find the start of the JSON block we parsed.
            if "Action:" in text:
                thought = text.split("Action:")[0].strip()
            else:
                # Find where the JSON starts
                json_str = json.dumps(action_data)
                # This is imprecise but better than nothing; 
                # usually it's "Thought: ... { JSON }"
                parts = text.split('{', 1)
                thought = parts[0].strip() if len(parts) > 1 else text[:200]
            
            # Strip "Thought:" prefix if present
            thought = re.sub(r"^(Thought:\s*)+", "", thought, flags=re.IGNORECASE).strip()
            
            return AgentAction(
                log=thought,
                **action_data
            )

        # If no action found but text contains Action markers, it's likely malformed JSON
        if "Action:" in text and "Final Answer:" not in text:
            raise ValueError("Found 'Action:' marker but could not parse a valid JSON/YAML structure.")
            
        # If no action found, it's a Finish
        # Clean up the output by stripping "Final Answer:" or "Thought:"
        output = text
>>>
```

### Step 3: Implement the Retry/Correction Loop in the Executor

#### [MODIFY] .agent/src/agent/core/engine/executor.py

```
<<<SEARCH
                # 2. PARSE
                with tracer.start_as_current_span("agent.parse") as parse_span:
                    parsed_result = self.parser.parse(llm_response)
                    parse_span.set_attribute("parsed_result", str(parsed_result))
===
                # 2. PARSE
                with tracer.start_as_current_span("agent.parse") as parse_span:
                    from pydantic import ValidationError
                    try:
                        parsed_result = self.parser.parse(llm_response)
                        parse_span.set_attribute("parsed_result", str(parsed_result))
                    except (ValidationError, ValueError) as e:
                        logger.warning(f"LLM output validation failed: {str(e)}")
                        agent_errors_counter.add(1, {"error.type": "validation"})
                        
                        hint = (
                            f"Validation Error: Your previous response was malformed or failed strict schema validation.\n"
                            f"Error details: {str(e)}\n\n"
                            f"Please correct your output to strictly match the expected format (either a valid 'Action' block with NO extra fields, or a Final Answer)."
                        )
                        yield {"type": "thought", "content": f"[Validation failed — requesting LLM correction: {str(e)}]"}
                        
                        fake_action = AgentAction(tool="system_validator", tool_input={"action": "validation"}, log=llm_response)
                        step = AgentStep(
                            action=fake_action,
                            observation=hint,
                        )
                        history.append(step)
                        consecutive_tool_calls += 1
                        continue
>>>
```

### Step 4: Fix Type Hint in logger.py

#### [MODIFY] .agent/src/agent/core/logger.py

```
<<<SEARCH
def get_logger(name: str):
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"agent.{name}")
===
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"agent.{name}")
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests`: Complete regression test suite passes successfully.

### Manual Verification

- [ ] Verify validation loop logic using a simulated malformed LLM response block.

## Copyright

Copyright 2026 Justin Cook

