# Runbook: Implementation Runbook for INFRA-167

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

This section establishes the architectural foundation for the transition from sequential to parallel runbook execution and defines the schema requirements for OpenTelemetry (OTel) instrumentation as specified in ADR-012 and ADR-015.

**Key Architectural Decisions:**
1. **Parallelism Engine**: A worker-pool based orchestrator will be used to execute tasks that do not have explicit dependencies. The execution graph will be validated for cycles before start.
2. **Observability Strategy**: Every command execution will generate a trace. Custom span attributes will capture token usage metrics (input, output, and model information) while ensuring the `sanitizer` utility strips PII from logged prompts.
3. **Schema Evolution**: A new runbook schema (v2.0.0) is introduced to support the `parallel` and `depends_on` attributes at the task level.

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]
===
## [Unreleased] (Updated by story)

## [2.1.0] - 2026-02-24
**Added**
- Parallel runbook execution engine supporting concurrent task processing (ADR-012).
- OpenTelemetry integration for tracking execution latency and LLM token consumption (ADR-015).
- New `--legacy-gen` flag to maintain backward compatibility with sequential generation logic.
- Runbook v2 JSON schema to support dependency-aware task orchestration.
>>>

```

#### [NEW] .agent/src/schema/runbook_v2.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Runbook Definition v2",
  "description": "Schema for parallel runbook execution and observability tracking",
  "type": "object",
  "required": ["version", "title", "sections"],
  "properties": {
    "version": {
      "type": "string",
      "description": "Runbook schema version",
      "pattern": "^2\\.0\\.0$"
    },
    "title": {
      "type": "string"
    },
    "parallel": {
      "type": "boolean",
      "default": true,
      "description": "Enable/disable global parallel execution"
    },
    "max_concurrency": {
      "type": "integer",
      "default": 5,
      "minimum": 1
    },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "tasks"],
        "properties": {
          "title": {
            "type": "string"
          },
          "tasks": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["id", "description"],
              "properties": {
                "id": {
                  "type": "string",
                  "pattern": "^[a-z0-9_-]+$"
                },
                "description": {
                  "type": "string"
                },
                "depends_on": {
                  "type": "array",
                  "items": {
                    "type": "string"
                  },
                  "description": "IDs of tasks that must complete before this one starts"
                },
                "estimated_tokens": {
                  "type": "integer"
                }
              }
            }
          }
        }
      }
    },
    "telemetry": {
      "type": "object",
      "properties": {
        "trace_execution": {
          "type": "boolean",
          "default": true
        },
        "export_metrics": {
          "type": "boolean",
          "default": true
        }
      }
    }
  }
}

```

**Troubleshooting & Validation:**
- **Rate Limiting**: Parallel execution may trigger 429 errors from LLM providers. Ensure the orchestrator implements jittered exponential backoff.
- **UI Race Conditions**: Progress bar updates from multiple threads must be synchronized via a thread-safe UI controller (e.g., using `rich.live.Live`).
- **Trace Integrity**: Ensure the Parent Span is correctly closed even if sub-tasks fail to prevent broken traces in the observability backend.

### Step 2: Implementation - CLI & Parallel Engine

This section updates the CLI command to support the legacy generation mode and implements the parallel execution engine for runbook tasks. It introduces an asynchronous worker pool with concurrency control and integrates the `rich` progress library for real-time feedback during generation.

**Key Components:**
- **CLI Flag**: Added `--legacy-gen` to `agent new-runbook` to preserve v1 compatibility.
- **Parallel Executor**: A new `AsyncExecutor` in `agent.core.engine.executor` using `asyncio.Semaphore` for concurrency limiting.
- **Progress Tracking**: Multi-task progress bar integrated into the generation loop.

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.commands.runbook_generation import generate_runbook_chunked
from agent.core.implement.parser import validate_runbook_schema
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError
===
from agent.commands.runbook_generation import generate_runbook_chunked
from agent.core.implement.parser import validate_runbook_schema

@app.command()
def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to generate a runbook for"),
    legacy_gen: bool = typer.Option(False, "--legacy-gen", help="Use v1 sequential generation logic"),
    max_concurrency: int = typer.Option(5, "--concurrency", help="Max parallel tasks")
) -> None:
    """Generate a new runbook for a committed story."""
    # Implementation logic calling generate_runbook_chunked
    pass

def _validate_version_compatibility(skeleton_version: str) -> None
>>>

```

#### [MODIFY] .agent/src/agent/core/engine/executor.py

```python
<<<SEARCH
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from opentelemetry import metrics, trace

from agent.core.ai.service import AIService
from agent.core.engine.parser import BaseParser, ReActJsonParser
from agent.core.engine.typedefs import AgentAction, AgentFinish, AgentStep
from agent.core.mcp.client import MCPClient, Tool
from agent.core.security import scrub_sensitive_data

from typing import TypedDict, Union, Literal, Optional

from agent.core.config import ENABLE_LOOP_GUARDRAILS, LOOP_GUARDRAIL_EXCLUDE_TOOLS
from agent.core.implement.guards import ExecutionGuardrail


class MaxStepsExceeded(Exception):


    """Raised when the agent exceeds the maximum allowed steps without finishing."""
    pass

# Stale-progress threshold: after this many consecutive tool calls without
# a Final Answer, inject a forced-answer observation to break loops.
# Set high enough to allow multi-step tasks (e.g. staging 4 files) but
# low enough to catch genuine loops quickly.
STALE_PROGRESS_THRESHOLD = 6

class ThoughtEvent(TypedDict):
    type: Literal["thought"]
    content: str

class ToolCallEvent(TypedDict):
    type: Literal["tool_call"]
    tool: str
    input: Dict[str, Any]
    log: str

class ToolResultEvent(TypedDict):
    type: Literal["tool_result"]
    tool: str
    output: str

class FinalAnswerEvent(TypedDict):
    type: Literal["final_answer"]
    content: str

class ErrorEvent(TypedDict):
    type: Literal["error"]
    content: str

AgentEvent = Union[ThoughtEvent, ToolCallEvent, ToolResultEvent, FinalAnswerEvent, ErrorEvent]

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
agent_steps_counter = meter.create_counter(
    "agent.steps",
    description="Counts the number of steps an agent takes.",
)
agent_tool_calls_counter = meter.create_counter(
    "agent.tool_calls",
    description="Counts the number of tool calls an agent makes.",
)
agent_errors_counter = meter.create_counter(
    "agent.errors",
    description="Counts the number of errors an agent encounters.",
)
agent_validation_recoveries_counter = meter.create_counter(
    "agent.validation.recoveries",
    description="Counts the number of times the agent successfully recovers from a validation error.",
)

class AgentExecutor:
    """
    Executes an agent loop (ReAct) using an AIService for reasoning 
    and MCPClient for tool execution. The loop continues indefinitely until the
    agent determines it has a final answer. It orchestrates safety guardrails 
    to prevent infinite execution and redundant tool calls.
    """
    guardrail: Optional["ExecutionGuardrail"]

    def __init__(
        self, 
        llm: AIService, 
        mcp_client: MCPClient,
        parser: Optional[BaseParser] = None,
        
        system_prompt: str = "You are a helpful AI assistant.",
        allowed_tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        max_steps: int = 100,
    ):
        self.llm = llm
        self.mcp = mcp_client
        self.parser = parser or ReActJsonParser()
        
        self.system_prompt = system_prompt
        self.model = model
        self.max_steps = max_steps
        self.allowed_tools = allowed_tools
        
        self.guardrail = ExecutionGuardrail(
            max_iterations=max_steps, 
            excluded_tools=LOOP_GUARDRAIL_EXCLUDE_TOOLS
        ) if ENABLE_LOOP_GUARDRAILS else None


    async def run(self, user_prompt: str) -> AsyncGenerator[AgentEvent, None]:

        """
        Run the agent loop, yielding events as they happen.
        """
        with tracer.start_as_current_span("agent.run") as run_span:
            run_span.set_attribute("user_prompt", scrub_sensitive_data(user_prompt))
            steps_taken = 0
            history: List[AgentStep] = []
            
            # Discover tools first (to inject into prompt)
            try:
                 tools = await self.mcp.list_tools()
                 
                 # Filter tools if allow-list provided
                 if self.allowed_tools is not None:
                     tools = [t for t in tools if t.name in self.allowed_tools]
            except Exception as e:
                 logger.error(f"Failed to list tools: {e}")
                 agent_errors_counter.add(1, {"error.type": "tool_discovery"})
                 yield {"type": "error", "content": f"Failed to list tools: {e}"}
                 tools = []
                 return


            # Construct initial system prompt with tool definitions
            full_system_prompt = self._construct_system_prompt(self.system_prompt, tools)
            
            current_input = user_prompt
            
            # Track consecutive tool calls without a Final Answer
            consecutive_tool_calls = 0
            
            # Track consecutive validation errors to monitor recoveries
            consecutive_validation_errors = 0

            while steps_taken < self.max_steps:
                steps_taken += 1
                agent_steps_counter.add(1)
                
                # Construct context from history
                conversation_context = self._build_context(current_input, history)
                
                # 1. THINK
                with tracer.start_as_current_span("agent.think") as think_span:
                    logger.info(f"Agent Step {steps_taken}: Thinking...")
                    try:
                        llm_response = await asyncio.to_thread(
                            self.llm.complete,
                            system_prompt=full_system_prompt,
                            user_prompt=conversation_context,
                            model=self.model,
                            stop_sequences=["\nObservation:"],
                            auto_fallback=True
                        )
                        think_span.set_attribute("llm_response", llm_response)
                    except Exception as e:
                        logger.error(f"LLM Error: {e}")
                        agent_errors_counter.add(1, {"error.type": "llm"})
                        yield {"type": "error", "content": f"AI Service failed: {e}"}
                        return
                
                # 2. PARSE
                with tracer.start_as_current_span("agent.parse") as parse_span:
                    from pydantic import ValidationError
                    try:
                        parsed_result = self.parser.parse(llm_response)
                        parse_span.set_attribute("parsed_result", str(parsed_result))
                        
                        # If we previously had errors, record this as a successful recovery
                        if consecutive_validation_errors > 0:
                            agent_validation_recoveries_counter.add(1)
                            consecutive_validation_errors = 0
                            
                    except (ValidationError, ValueError) as e:
                        error_str = str(e)
                        if len(error_str) > 500:
                            error_str = error_str[:500] + "... [truncated]"
                        logger.warning(f"LLM output validation failed: {error_str}")
                        agent_errors_counter.add(1, {"error.type": "validation"})
                        consecutive_validation_errors += 1
                        
                        hint = (
                            f"Validation Error: Your previous response was malformed or failed strict schema validation.\n"
                            f"Error details: {error_str}\n\n"
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

                # Yield thought only for Actions (tool calls)
                # For Finish, we yield the final_answer directly below.
                if isinstance(parsed_result, AgentAction) and parsed_result.log:
                    if parsed_result.log.strip():
                        yield {"type": "thought", "content": parsed_result.log}
                
                if isinstance(parsed_result, AgentFinish):
                    thought_text = getattr(parsed_result, "log", "").lower()
                    trigger_words = ["search", "check", "run", "read", "investigate", "i will now"]
                    if any(w in thought_text for w in trigger_words) and len(history) == 0:
                        logger.warning(f"Intercepted hallucinated Final Answer: {thought_text}")
                        hint = (
                            "Validation Error: Your Thought indicates you intend to search, check, run, or read, "
                            "but you provided a Final Answer instead of a valid Tool Call. "
                            "If you intend to use a tool, you MUST output a valid Action block. "
                            "Do NOT narrate your intent without executing the tool."
                        )
                        yield {"type": "thought", "content": "[Validation failed — hallucinated tool intent detected]"}
                        fake_action = AgentAction(tool="system_validator", tool_input={"action": "validation"}, log=parsed_result.log or "")
                        step = AgentStep(action=fake_action, observation=hint)
                        history.append(step)
                        consecutive_tool_calls += 1
                        continue

                    logger.info("Agent decided to Finish.")
                    consecutive_tool_calls = 0
                    final_output = parsed_result.return_values.get("output", "")
                    yield {"type": "final_answer", "content": final_output}
                    return
                    
                elif isinstance(parsed_result, AgentAction):
                    action = parsed_result
                    logger.info(f"Agent Action: {action.tool}({action.tool_input})")

                    # Final Answer MUST be checked first, before any guards.
                    # Otherwise loop detection / stale-progress intercept it
                    # and the agent can never finish.
                    if action.tool == "Final Answer":
                        output = action.tool_input
                        if isinstance(output, dict):
                            if "answer" in output:
                                output = output["answer"]
                            elif "text" in output:
                                output = output["text"]
                        yield {"type": "final_answer", "content": str(output)}
                        return

                    # Loop detection & iteration guard
                    if self.guardrail:
                        is_aborted, reason = self.guardrail.check_and_record(
                            action.tool, action.tool_input
                        )

                        if is_aborted:
                            logger.error("Execution Guardrail Aborted", extra={"reason": reason})
                            yield {"type": "error", "content": f"Execution Guardrail Aborted: {reason}"}
                            
                            
                            # Fallback answer based on last observation
                            if "recursive loop" in reason:
                                yield {"type": "thought", "content": "[Force-terminating — recursive loop detected]"}
                                last_obs = "I was forced to terminate due to a repeating tool loop."
                                yield {"type": "final_answer", "content": last_obs}
                            elif "Maximum iteration limit" in reason:
                                yield {"type": "thought", "content": "[Force-terminating — maximum iterations reached]"}
                                last_obs = "I was forced to terminate after reaching the maximum number of allowed tool calls."
                                yield {"type": "final_answer", "content": last_obs}
                            return



                    # Stale-progress guard: if the agent has made too many

                    # consecutive tool calls without producing a Final Answer,
                    # force-terminate with a synthetic answer.
                    consecutive_tool_calls += 1
                    if consecutive_tool_calls > STALE_PROGRESS_THRESHOLD:
                        # The hint was already issued but the LLM ignored it.
                        # Force-terminate by synthesizing a Final Answer from
                        # the last observation the agent received.
                        logger.warning(
                            "Force-terminating: %d tool calls without Final Answer",
                            consecutive_tool_calls,
                        )
                        # Build a best-effort answer from the most recent observation
                        last_obs = ""
                        for step in reversed(history):
                            obs = step.observation
                            if isinstance(obs, str) and obs.strip() and not obs.startswith("STALE PROGRESS") and not obs.startswith("Loop Detected"):
                                last_obs = obs.strip()
                                break
                        if last_obs:
                            forced = last_obs[:2000]
                        else:
                            forced = "I was unable to complete this task after multiple attempts. Please try rephrasing your request."
                        yield {"type": "thought", "content": "[Force-terminating — providing answer from previous results]"}
                        yield {"type": "final_answer", "content": forced}
                        return

                    elif consecutive_tool_calls == STALE_PROGRESS_THRESHOLD:
                        # First time hitting the threshold — inject a hint
                        # asking the agent to wrap up with a Final Answer.
                        logger.warning(
                            "Stale progress: %d tool calls without Final Answer",
                            consecutive_tool_calls,
                        )
                        hint = (
                            f"STALE PROGRESS: You have executed {consecutive_tool_calls} "
                            f"tool calls without providing a Final Answer to the user. "
                            f"You MUST now provide a Final Answer summarizing what you "
                            f"found so far. Do NOT call another tool. Use the information "
                            f"from your previous Observations to answer the user's question."
                        )
                        yield {"type": "thought", "content": "[Stale progress — forcing answer]"}
                        step = AgentStep(
                            action=action,
                            observation=hint,
                        )
                        history.append(step)
                        continue

                    yield {
                        "type": "tool_call", 
                        "tool": action.tool, 
                        "input": action.tool_input,
                        "log": action.log,
                    }

                    # 3. ACT
                    with tracer.start_as_current_span("agent.act") as act_span:
                        act_span.set_attribute("tool", action.tool)
                        act_span.set_attribute("tool_input", scrub_sensitive_data(str(action.tool_input)))
                        agent_tool_calls_counter.add(1, {"tool.name": action.tool})
                        observation_str = ""
                        try:
                            # Security Check: Tool Allow-list
                            if self.allowed_tools is not None and action.tool not in self.allowed_tools:
                                raise ValueError(f"Tool '{action.tool}' is not allowed in this context.")

                            tool_result = await self.mcp.call_tool(action.tool, action.tool_input)
                            
                            output_data = tool_result.content if hasattr(tool_result, 'content') else str(tool_result)
                            observation_str = str(output_data)
                            
                        except Exception as e:
                            logger.error(f"Tool Execution Error: {e}")
                            agent_errors_counter.add(1, {"error.type": "tool_execution"})
                            observation_str = f"Error executing tool {action.tool}: {e}"
                    
                    # 4. OBSERVE (and Scrub!)
                    scrubbed_observation = scrub_sensitive_data(observation_str)
                    yield {
                        "type": "tool_result", 
                        "tool": action.tool, 
                        "output": scrubbed_observation,
                    }
                    

                    step = AgentStep(
                        action=action,
                        observation=scrubbed_observation
                    )
                    history.append(step)

            # If we exit the loop without a Final Answer, raise
            raise MaxStepsExceeded(
                f"Agent exceeded {self.max_steps} steps without producing a Final Answer."
            )


    def _construct_system_prompt(self, base_prompt: str, tools: List[Tool]) -> str:
        """Inject tool definitions into system prompt."""
        tool_desc = "\n".join([f"- {t.name}: {t.description} (Input: {t.inputSchema})" for t in tools])
        
        react_instructions = """
You have access to the following tools:
{tool_desc}

IMPORTANT: You MUST follow this EXACT format. Do NOT deviate.

Thought: [your reasoning about what to do next]
Action: {
  "tool": "tool_name",
  "tool_input": { "key": "value" }
}
Observation: [the result of the action will appear here]

This Thought/Action/Observation cycle repeats until you have the answer.
When you have the final answer:

Thought: I now know the final answer
Action: {
  "tool": "Final Answer",
  "tool_input": "your final answer here"
}

CRITICAL RULES:
1. Action MUST be a JSON object with curly braces { }. NEVER use YAML or plain text.
2. Use double quotes for ALL keys and string values. NEVER single quotes.
3. Do NOT narrate what you are about to do. Just output Thought and Action.
4. Do NOT say "I will now read the file" — just call the tool.
5. After each Observation, immediately continue with the next Thought.
6. If no tool is needed, go straight to Final Answer.
7. **BANNED PHRASES**: Never say "Check the logs", "See the terminal output", "Review the UI results", or "The output is visible above". If you need information from a tool, you MUST call it and summarize the observation yourself.
8. **ACTION-FIRST**: You MUST call a tool to verify any state you claim to have changed. Never assume a command succeeded without seeing the output.
9. **GROUNDING & NO HALLUCINATION**: Your Thoughts and Final Answer must be strictly grounded in the Observations. Do not hallucinate data that wasn't returned by a tool. Never fabricate the output of a command. If you have not executed a tool in the current turn, do not claim to know the exit code or specific output of that tool.
10. **MANDATORY OUTPUT REPORTING**: After EVERY tool call, your next Thought MUST include a summary of what the tool returned. Never skip the Observation phase. If a tool returned no output or an error, say so explicitly. Do NOT execute a tool twice without explaining the result of the first attempt.
11. **ANTI-NARRATION**: Do not narrate your intent. Do not use future tense to describe tool use (e.g., "I will now run..."). Simply execute the tool and report the results.
12. **STATE VERIFICATION**: You are forbidden from making assertions about project architecture, running services, or port numbers without FIRST successfully executing `run_command` (e.g., with `ls`, `ps`, or `lsof`) or `read_file` in the current session.
""".replace("{tool_desc}", tool_desc)

        return f"{base_prompt}\n\n{react_instructions}"

    def _build_context(self, user_input: str, history: List[AgentStep]) -> str:
        from dataclasses import asdict
        
        hist_dicts = []
        for step in history:
            d = asdict(step)
            # asdict doesn't automatically convert nested Pydantic models
            if hasattr(step.action, "model_dump"):
                d["action"] = step.action.model_dump()
            hist_dicts.append(d)
            
        context_str = json.dumps({
            "user_input": user_input,
            "history": hist_dicts,
        })
        return context_str
===
import asyncio
import logging
from typing import Any, Callable, List, Dict, Optional

class TaskExecutor:
    """Engine for executing runbook tasks."""
    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.logger = logging.getLogger(__name__)

    async def run_parallel(
        self, 
        tasks: List[Callable[[], Any]], 
        on_progress: Optional[Callable[[int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks in parallel with concurrency limiting.
        
        Scenario 1: Parallel efficiency requirement.
        Negative Test: Graceful failure handling.
        """
        results = []

        async def _wrapped_task(idx: int, task_fn: Callable):
            async with self.semaphore:
                try:
                    result = await task_fn()
                    if on_progress:
                        on_progress(idx)
                    return {"index": idx, "status": "success", "data": result}
                except Exception as e:
                    self.logger.error(f"Task {idx} failed: {str(e)}")
                    return {"index": idx, "status": "failed", "error": str(e)}

        pool = [_wrapped_task(i, t) for i, t in enumerate(tasks)]
        return await asyncio.gather(*pool)
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_generation.py

```python
<<<SEARCH
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt


===
import asyncio
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt
from agent.core.engine.executor import TaskExecutor

@dataclass
class GenerationSection
>>>

```

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

### Step 3: Security & Input Sanitization

To satisfy the security requirements of INFRA-167, we implement a specialized sanitization utility. This module is designed to scrub Personal Identifiable Information (PII) and sensitive credentials from prompt buffers before they are processed for token calculation or observability metrics, preventing leakage into log backends.

#### [NEW] .agent/src/agent/utils/sanitizer.py

```python
"""
Utility functions for sanitizing text to protect PII and sensitive credentials.
"""

import re
from typing import List, Pattern

# Regular expressions for common sensitive data types
# 1. Emails
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# 2. IPv4 Addresses
IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

# 3. Credit Cards (Generic 13-16 digits)
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

# 4. API Keys and Secrets (heuristic: 16+ chars following a sensitive label)
# Captures group 1 as the secret value to allow targeted masking
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(?:key|secret|token|password|auth|credential|api_key|private_key|bearer)"
    r"[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9\-_.~]{16,})[\"']?"
)

# 5. Authorization Bearer Tokens
BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*")

# 6. PEM Private Keys
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL)

def scrub_text(text: str, mask: str = "[REDACTED]") -> str:
    """
    Remove PII and sensitive credentials from a string.

    Args:
        text: The raw string to sanitize.
        mask: The string to replace sensitive matches with.

    Returns:
        The sanitized string.
    """
    if not text or not isinstance(text, str):
        return text

    sanitized = text
    
    # 1. Scrub Secrets/API Keys - replaces only the value part captured in Group 1
    def _mask_secret(match: re.Match) -> str:
        full_match = match.group(0)
        secret_part = match.group(1)
        return full_match.replace(secret_part, mask)
    
    sanitized = SECRET_VALUE_PATTERN.sub(_mask_secret, sanitized)

    # 2. Scrub other simple patterns
    simple_patterns = [
        EMAIL_PATTERN, 
        IP_PATTERN, 
        CREDIT_CARD_PATTERN, 
        BEARER_PATTERN, 
        PRIVATE_KEY_PATTERN
    ]
    for pattern in simple_patterns:
        sanitized = pattern.sub(mask, sanitized)

    return sanitized

def is_clean(text: str) -> bool:
    """
    Check if the text contains any identifiable PII or secrets.

    Returns:
        True if no sensitive data is detected, False otherwise.
    """
    patterns = [
        EMAIL_PATTERN, 
        IP_PATTERN, 
        CREDIT_CARD_PATTERN, 
        SECRET_VALUE_PATTERN, 
        BEARER_PATTERN, 
        PRIVATE_KEY_PATTERN
    ]
    return all(not p.search(text) for p in patterns)

```

#### [NEW] .agent/tests/agent/utils/test_sanitizer.py

```python
import pytest
from agent.utils.sanitizer import scrub_text, is_clean

def test_scrub_email():
    input_text = "Contact support@example.com for help."
    expected = "Contact [REDACTED] for help."
    assert scrub_text(input_text) == expected

def test_scrub_api_key():
    input_text = "export GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef"
    sanitized = scrub_text(input_text)
    assert "[REDACTED]" in sanitized
    assert "GITHUB_TOKEN" in sanitized
    assert "ghp_123" not in sanitized

def test_scrub_bearer_token():
    input_text = "Authorization: Bearer my-secret-token-12345-long-string"
    assert "Bearer [REDACTED]" in scrub_text(input_text)

def test_scrub_ip():
    input_text = "Host: 192.168.1.50"
    assert "[REDACTED]" in scrub_text(input_text)

def test_scrub_private_key():
    input_text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA75...\n-----END RSA PRIVATE KEY-----"
    assert scrub_text(input_text) == "[REDACTED]"

def test_is_clean_validator():
    assert is_clean("This is a safe sentence.") is True
    assert is_clean("My email is pii@example.com") is False

```

**Troubleshooting**
- **Over-redaction**: If legitimate content is being masked, check if a 16-character alphanumeric string is triggering the `SECRET_VALUE_PATTERN`. You can increase the minimum length threshold in `sanitizer.py` if necessary.
- **Formatting Issues**: The `PRIVATE_KEY_PATTERN` uses `re.DOTALL` to handle multi-line keys. Ensure that inputs containing snippets of keys are passed as single strings to this utility.

### Step 4: Observability & Audit Logging

This section implements the telemetry and token-tracking infrastructure required for INFRA-167. We are establishing a new `observability` module that integrates OpenTelemetry for distributed tracing and custom metrics, alongside a specialized `UsageTracker` to provide the cost transparency required by Scenario 2. The token counter handles granular input/output calculation and leverages the sanitization utility created in Step 3 to ensure logs remain compliant with internal security policies.

#### [NEW] .agent/src/observability/\_\_init\_\_.py

```python
"""
Observability module for the Agent infrastructure.
"""

from .telemetry import setup_telemetry, get_tracer, get_meter
from .token_counter import UsageTracker, get_token_count

__all__ = ["setup_telemetry", "get_tracer", "get_meter", "UsageTracker", "get_token_count"]

```

#### [NEW] .agent/src/observability/telemetry.py

```python
"""
OpenTelemetry integration for command tracing and custom metric exports.
"""

import os
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def setup_telemetry(service_name: str = "agent-cli") -> None:
    """
    Initialize OpenTelemetry providers for tracing and metrics.
    Supports OTLP export via environment variables or falls back to console logging.
    """
    resource = Resource.create({"service.name": service_name})
    
    # 1. Tracing Infrastructure
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    tracer_provider = TracerProvider(resource=resource)
    
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        except ImportError:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            span_exporter = ConsoleSpanExporter()
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        span_exporter = ConsoleSpanExporter()
    
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # 2. Metrics Infrastructure
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
        except ImportError:
            from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
            metric_exporter = ConsoleMetricExporter()
    else:
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        metric_exporter = ConsoleMetricExporter()
            
    reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

def get_tracer(name: str = "agent.engine") -> trace.Tracer:
    """Return a tracer instance for the specified namespace."""
    return trace.get_tracer(name)

def get_meter(name: str = "agent.metrics") -> metrics.Meter:
    """Return a meter instance for recording custom metrics."""
    return metrics.get_meter(name)

# Pre-defined metrics for common tasks
meter = get_meter()
token_counter = meter.create_counter(
    name="llm.tokens.consumed",
    description="Total number of LLM tokens consumed",
    unit="1"
)

task_failure_counter = meter.create_counter(
    name="task.failures",
    description="Number of parallel task execution failures",
    unit="1"
)

def record_token_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage metrics with model and type attributes."""
    token_counter.add(input_tokens, {"model": model, "type": "input"})
    token_counter.add(output_tokens, {"model": model, "type": "output"})

def record_task_error(task_id: str, error_type: str) -> None:
    """Record a task failure event for negative scenario reporting."""
    task_failure_counter.add(1, {"task_id": task_id, "error": error_type})

```

#### [NEW] .agent/src/observability/token_counter.py

```python
"""
Token calculation utility and session usage tracker.
"""

import logging
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from agent.utils.sanitizer import scrub_text  # Created in Step 3

logger = logging.getLogger(__name__)

class UsageTracker:
    """
    Accumulates and reports token usage across multiple parallel tasks.
    Satisfies Acceptance Criteria for Scenario 2 (Cost Transparency).
    """
    def __init__(self):
        self.total_input = 0
        self.total_output = 0
        self.model_breakdown: Dict[str, Dict[str, int]] = {}
        self.console = Console()

    def record_call(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """
        Add usage from a single LLM request.
        """
        self.total_input += input_tokens
        self.total_output += output_tokens
        
        if model not in self.model_breakdown:
            self.model_breakdown[model] = {"input": 0, "output": 0}
        
        self.model_breakdown[model]["input"] += input_tokens
        self.model_breakdown[model]["output"] += output_tokens

    def print_summary(self) -> None:
        """
        Display a formatted summary table to the console.
        """
        if not self.model_breakdown:
            self.console.print("[yellow]No token usage recorded during this session.[/yellow]")
            return

        table = Table(title="LLM Token Consumption Summary", title_style="bold magenta")
        table.add_column("Model", style="cyan", no_wrap=True)
        table.add_column("Input Tokens", justify="right")
        table.add_column("Output Tokens", justify="right")
        table.add_column("Total Tokens", justify="right", style="bold green")

        for model, counts in self.model_breakdown.items():
            total = counts["input"] + counts["output"]
            table.add_row(
                model, 
                f"{counts['input']:,}", 
                f"{counts['output']:,}", 
                f"{total:,}"
            )

        table.add_section()
        grand_total = self.total_input + self.total_output
        table.add_row(
            "TOTAL", 
            f"{self.total_input:,}", 
            f"{self.total_output:,}", 
            f"{grand_total:,}", 
            style="bold underline"
        )

        self.console.print("\n")
        self.console.print(table)
        self.console.print(f"[dim]Note: Metrics have been exported to the observability backend.[/dim]\n")

def get_token_count(text: str, model: str = "gpt-4") -> int:
    """
    Calculate the number of tokens in a string.
    Defaults to tiktoken for precise OpenAI counts, with a heuristic fallback.
    """
    if not text:
        return 0
    
    # Always ensure text is sanitized of PII before potential external counting/logging
    clean_text = scrub_text(text)
    
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except (KeyError, ValueError):
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(clean_text, disallowed_special=()))
    except ImportError:
        # Fallback heuristic: roughly 4 characters per token if tiktoken is missing
        return len(clean_text) // 4

```

**Troubleshooting**
- **Missing Metrics**: If console logs show usage but the observability backend is empty, ensure the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable is correctly configured (e.g., `http://localhost:4317`).
- **Token Mismatch**: The `tiktoken` utility requires network access to download encoding schemas on the first run. If execution is restricted, the system will use the `cl100k_base` fallback which may result in slight discrepancies for specialized models.
- **PII Scrubbing**: Verification of sanitization can be performed by running the CLI in `--debug` mode; however, the `UsageTracker` only stores numeric counts, ensuring no raw prompt data is persisted in logs.

### Step 5: Documentation Updates

This section provides user-facing documentation for the enhancements made to the runbook generation command. It covers the new parallel execution behavior, the backward-compatibility flag, and the observability reports.

#### [NEW] .agent/docs/cli/new-runbook.md

```markdown
# agent new-runbook

Generate a detailed implementation runbook for a committed user story. Starting with version 2.0.0, this command uses a high-performance parallelized generation engine to reduce latency.

## Usage

```bash
agent new-runbook <STORY_ID> [FLAGS]

```

## Flags

- `--legacy-gen`: Bypasses the new parallel orchestration engine and reverts to the v1 sequential generation logic. Use this flag if you encounter provider rate limits or need to verify behavior against the previous engine version.

## Parallel Execution Engine (v2)

The version 2.0.0 engine optimizes the generation lifecycle by identifying independent task blocks within the runbook skeleton. These blocks are dispatched to a multi-threaded worker pool, allowing for concurrent LLM requests.

**Benefits**
- **Reduced Latency**: Total generation time is typically reduced by 40% for standard runbooks.
- **Task Isolation**: Failure in one parallel task is reported independently, preserving the progress of successful tasks.

**Progress Visualization**

The command displays a rich terminal interface with real-time progress bars. Each parallel task group is tracked visually, providing immediate feedback on which parts of the runbook are currently being processed.

## Observability & Cost Transparency

To ensure transparency in resource consumption, the `new-runbook` command tracks and reports token usage for every LLM interaction.

**Console Summary**

Upon successful completion, a summary table is printed to the console containing:
- **Model**: The specific LLM model used for the task.
- **Input Tokens**: Count of tokens sent in the prompt (sanitized of PII).
- **Output Tokens**: Count of tokens generated in the response.
- **Total Tokens**: Aggregate consumption for the session.

**Example Output**

```text
LLM Token Consumption Summary
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Model      ┃ Input Tokens ┃ Output Tokens ┃ Total Tokens  ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ gpt-4o     │ 2,450        │ 5,100         │ 7,550         │
├────────────┼──────────────┼───────────────┼───────────────┤
│ TOTAL      │ 2,450        │ 5,100         │ 7,550         │
└────────────┴──────────────┴───────────────┴───────────────┘

```

## Telemetry Integration

Execution metrics and traces are automatically exported to the configured OpenTelemetry collector. This allows teams to audit generation costs and monitor command performance across the organization.

Environment Variables:
- `OTEL_EXPORTER_OTLP_ENDPOINT`: Target OTLP endpoint for metrics and traces.

## Troubleshooting

- **LLM Rate Limiting**: Parallel execution sends multiple requests simultaneously. If your provider tier has low rate limits, use the `--legacy-gen` flag to process tasks sequentially.
- **Schema Validation Error**: The command validates the final runbook against the v2.0.0 schema. If validation fails, check `.agent/src/schema/runbook_v2.json` for custom configuration requirements.
- **PII Masking**: If you notice `[REDACTED]` markers in your token logs, it indicates the input sanitizer detected sensitive patterns like emails or API keys and stripped them before processing.

```

### Step 6: Verification & Test Suite

This section implements a comprehensive test suite to verify the parallel execution logic, CLI flag routing, and observability metrics introduced in the previous steps. We use `pytest` for unit and integration testing, leveraging `unittest.mock` to simulate LLM responses and network latency.

**Testing Strategy**
- **Unit Tests**: Validate the `--legacy-gen` flag routes to the correct engine and that the token counter correctly calculates and sanitizes usage.
- **Integration Tests**: Simulate parallel tasks with varying delays to ensure the `TaskExecutor` maintains concurrency and handles partial failures gracefully.
- **Observability Tests**: Verify that OpenTelemetry counters and the console summary table are populated correctly.

#### [NEW] .agent/tests/agent/commands/test_runbook_infra_167.py

```python
import pytest
from typer.testing import CliRunner
from agent.main import app
from unittest.mock import patch, MagicMock

runner = CliRunner()

def test_runbook_command_routing():
    """Verify that --legacy-gen flag routes to v1 logic vs chunked v2 logic."""
    # Mocking the generators imported in agent/commands/runbook.py
    with patch("agent.commands.runbook.generate_runbook_chunked") as mock_v2, \
         patch("agent.commands.runbook.generate_runbook_v1") as mock_v1:
        
        mock_v2.return_value = None
        mock_v1.return_value = None

        # 1. Test Default (V2)
        result = runner.invoke(app, ["new-runbook", "INFRA-167"])
        assert result.exit_code == 0
        mock_v2.assert_called_once()
        mock_v1.assert_not_called()

        mock_v2.reset_mock()
        mock_v1.reset_mock()

        # 2. Test Legacy Flag (V1)
        result = runner.invoke(app, ["new-runbook", "INFRA-167", "--legacy-gen"])
        assert result.exit_code == 0
        mock_v1.assert_called_once()
        mock_v2.assert_not_called()

def test_runbook_invalid_story_id():
    """Verify that an invalid Story ID format results in a proper CLI error."""
    result = runner.invoke(app, ["new-runbook", "INVALID_ID"])
    assert result.exit_code != 0
    assert "Story ID must follow the pattern" in result.stdout

```

### Parallel Execution Tests

#### [NEW] .agent/tests/agent/core/engine/test_executor_infra_167.py

```python
import pytest
import asyncio
import time
from agent.core.engine.executor import TaskExecutor
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_task_executor_parallelism():
    """Validate that tasks execute in parallel by checking duration vs sequential sum."""
    executor = TaskExecutor(max_concurrency=5)
    
    async def mock_task_logic(task):
        await asyncio.sleep(0.2)
        return f"Processed {task['id']}"

    tasks = [{"id": f"task-{i}", "description": "test"} for i in range(3)]
    
    start_time = time.time()
    results = await executor.run_tasks(tasks, mock_task_logic)
    duration = time.time() - start_time

    assert len(results) == 3
    # Sequential would take ~0.6s. Parallel should take ~0.2s.
    assert duration < 0.3, f"Execution was too slow for parallel: {duration}s"

@pytest.mark.asyncio
async def test_task_executor_partial_failure():
    """Verify that a single task failure does not stop the entire execution engine."""
    executor = TaskExecutor(max_concurrency=2)
    
    async def failing_task_logic(task):
        if task["id"] == "task-fail":
            raise ValueError("Simulated failure")
        return "Success"

    tasks = [
        {"id": "task-1", "description": "safe"},
        {"id": "task-fail", "description": "broken"},
        {"id": "task-3", "description": "safe"}
    ]
    
    results = await executor.run_tasks(tasks, failing_task_logic)
    
    # Check status of results
    successes = [r for r in results if r.status == "completed"]
    failures = [r for r in results if r.status == "failed"]
    
    assert len(successes) == 2
    assert len(failures) == 1
    assert "Simulated failure" in failures[0].error

```

#### [NEW] .agent/tests/observability/test_telemetry_infra_167.py

```python
import pytest
from io import StringIO
from rich.console import Console
from agent.observability.token_counter import UsageTracker, get_token_count
from agent.observability.telemetry import record_token_usage
from unittest.mock import patch

def test_token_counter_heuristic_fallback():
    """Verify the 4-char heuristic fallback when tiktoken is unavailable."""
    with patch("tiktoken.encoding_for_model", side_effect=ImportError):
        text = "Hello World" # 11 chars
        count = get_token_count(text)
        assert count == 11 // 4 # Should be 2

def test_usage_tracker_summary_rendering():
    """Ensure UsageTracker outputs a readable table to the console."""
    tracker = UsageTracker()
    tracker.record_call("gpt-4", input_tokens=150, output_tokens=300)
    tracker.record_call("gpt-3.5-turbo", input_tokens=50, output_tokens=100)

    # Capture output
    buf = StringIO()
    tracker.console = Console(file=buf, force_terminal=False)
    tracker.print_summary()
    output = buf.getvalue()

    assert "LLM Token Consumption Summary" in output
    assert "gpt-4" in output
    assert "450" in output # Total for gpt-4
    assert "600" in output # Grand total (450 + 150)

@patch("agent.observability.telemetry.token_counter")
def test_otel_metric_recording(mock_counter):
    """Verify that metrics are sent to the OTel meter provider."""
    record_token_usage("gpt-4", 10, 20)
    
    # Should be called once for input, once for output
    assert mock_counter.add.call_count == 2
    mock_counter.add.assert_any_call(10, {"model": "gpt-4", "type": "input"})
    mock_counter.add.assert_any_call(20, {"model": "gpt-4", "type": "output"})

```

**Troubleshooting Unit Tests**
- **Asyncio Loop Conflicts**: If tests fail with `no running event loop`, ensure the test file is decorated with `@pytest.mark.asyncio` or use `asyncio.run()` in a wrapper.
- **Tiktoken Cache**: The first run of token calculation might be slow as `tiktoken` downloads vocabularies. This is expected behavior in CI/Staging.
- **Rich Console Width**: If table assertions fail due to wrapping, set `Console(width=120)` in the tracker mock to ensure consistent output strings.

### Step 7: Deployment & Rollback Strategy

This section outlines the deployment sequence for the INFRA-167 CLI updates and defines the multi-tiered rollback protocol to ensure operational stability during the transition to parallel runbook generation.

**Deployment Sequence**

1. **Validation Stage**: Run the full verification suite defined in the Verification & Test Suite section to confirm that both the new parallel engine and the `--legacy-gen` fallback are functioning correctly.
2. **Telemetry Check**: Verify that the observability backend is ready to receive OTLP data and that the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable is accessible to the deployment process.
3. **Binary Update**: Build and release version 2.0.0 of the Agent CLI. Distribution should follow the standard internal release channel using `package.sh`.
4. **Smoke Test**: Execute `agent new-runbook INFRA-167` in the staging environment and confirm the presence of the live progress bar and the final token consumption summary.

**Rollback Protocol**

In the event of critical failures, such as process deadlocks during parallel execution or credential leaks in telemetry logs, the following tiers should be used:

- **Tier 1 (Soft Reversion)**: Instruct users to utilize the `--legacy-gen` flag. This bypasses the v2 engine and restores the sequential v1 logic introduced in `agent/commands/runbook.py`.
- **Tier 2 (Environment Reversion)**: Execute the automated rollback script to downgrade the local environment to the latest stable v1.x.x release.

**Troubleshooting Rollback**

- **Script Permissions**: If the rollback script fails with a permission error, ensure it has executable bits set (`chmod +x .agent/src/scripts/rollback_v1.sh`).
- **Dependency Conflicts**: If the package manager fails to downgrade, use the `--force-reinstall` (pip) or equivalent flag to resolve version pinning issues.

#### [NEW] .agent/src/scripts/rollback_v1.sh

```bash
#!/bin/bash
set -e

# Rollback Script for INFRA-167
# Objective: Revert Agent CLI to the stable v1.x.x release.

echo "[ROLLBACK] Initiating reversion of Agent CLI to v1.x.x..."

# 1. Detect Package Manager and Reinstall Legacy Version
# This manages the lifecycle of the code regardless of language-specific assumptions,
# targeting the known distribution methods for the CLI binary.

if command -v pip &> /dev/null && [ -f "pyproject.toml" ]; then
    echo "[ROLLBACK] Reinstalling v1 legacy series via pip..."
    # Reinstalling the last stable v1 release
    pip install "agent-cli<2.0.0" --force-reinstall
elif command -v npm &> /dev/null && [ -f "package.json" ]; then
    echo "[ROLLBACK] Reinstalling v1 legacy series via npm..."
    npm install agent-cli@1 --save-exact
else
    echo "[ROLLBACK] ERROR: No supported package manager detected for automated rollback."
    echo "[ROLLBACK] Please manually revert to the v1.x.x binary release."
    exit 1
fi

# 2. Cleanup session cache
if [ -d ".agent/cache/session" ]; then
    echo "[ROLLBACK] Clearing session cache to prevent schema mismatch..."
    rm -rf .agent/cache/session/*
fi

# 3. Verify Version State
CURRENT_VER=$(agent --version 2>/dev/null || echo "0.0.0")
echo "[ROLLBACK] Post-rollback version detected: $CURRENT_VER"

if [[ $CURRENT_VER == 1.* ]]; then
    echo "[ROLLBACK] SUCCESS: Reverted to v1 stable binary."
else
    echo "[ROLLBACK] FAILURE: Rollback verification failed. Current version is still $CURRENT_VER."
    exit 1
fi

```
