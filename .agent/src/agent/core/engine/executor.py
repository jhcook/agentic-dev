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

from typing import TypedDict, Union, Literal

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
    agent determines it has a final answer.
    """
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

                    # Loop detection: if the agent attempts the exact same
                    # tool + input as the previous step, inject a hint instead
                    # of re-executing. This breaks infinite read-file loops.
                    if history:
                        prev = history[-1]
                        if (prev.action.tool == action.tool
                                and prev.action.tool_input == action.tool_input):
                            logger.info(
                                f"Loop detected: {action.tool} called with "
                                f"identical input twice consecutively."
                            )
                            hint = (
                                f"Loop Detected: You already called "
                                f"{action.tool} with these exact arguments "
                                f"in the previous step. The result was:\n"
                                f"{prev.observation[:500]}\n\n"
                                f"Use this result to proceed. Do NOT repeat "
                                f"the same tool call. Either process this "
                                f"output, try a different tool, or provide "
                                f"your Final Answer."
                            )
                            yield {"type": "thought", "content": "[Loop detected — reusing previous result]"}
                            step = AgentStep(
                                action=action,
                                observation=hint,
                            )
                            history.append(step)
                            consecutive_tool_calls += 1
                            continue

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

