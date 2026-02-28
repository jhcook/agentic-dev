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
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from opentelemetry import metrics, trace

from agent.core.ai.service import AIService
from agent.core.engine.parser import BaseParser, ReActJsonParser
from agent.core.engine.typedefs import AgentAction, AgentFinish, AgentStep
from agent.core.mcp.client import MCPClient, Tool
from agent.core.security import scrub_sensitive_data

from typing import TypedDict, Union, Literal

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

class MaxStepsExceeded(Exception):
    pass

class AgentExecutor:
    """
    Executes an agent loop (ReAct) using an AIService for reasoning 
    and MCPClient for tool execution.
    """
    def __init__(
        self, 
        llm: AIService, 
        mcp_client: MCPClient,
        parser: Optional[BaseParser] = None,
        max_steps: int = 10,
        system_prompt: str = "You are a helpful AI assistant.",
        allowed_tools: Optional[List[str]] = None,
        model: Optional[str] = None,
    ):
        self.llm = llm
        self.mcp = mcp_client
        self.parser = parser or ReActJsonParser()
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.model = model
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
                        )
                        think_span.set_attribute("llm_response", llm_response)
                    except Exception as e:
                        logger.error(f"LLM Error: {e}")
                        agent_errors_counter.add(1, {"error.type": "llm"})
                        yield {"type": "error", "content": "Error: AI Service failed."}
                        return
                
                # 2. PARSE
                with tracer.start_as_current_span("agent.parse") as parse_span:
                    parsed_result = self.parser.parse(llm_response)
                    parse_span.set_attribute("parsed_result", str(parsed_result))

                # Yield thought only for Actions (tool calls)
                # For Finish, we yield the final_answer directly below.
                if isinstance(parsed_result, AgentAction) and parsed_result.log:
                    if parsed_result.log.strip():
                        yield {"type": "thought", "content": parsed_result.log}
                
                if isinstance(parsed_result, AgentFinish):
                    logger.info("Agent decided to Finish.")
                    final_output = parsed_result.return_values.get("output", "")
                    yield {"type": "final_answer", "content": final_output}
                    return
                    
                elif isinstance(parsed_result, AgentAction):
                    action = parsed_result
                    logger.info(f"Agent Action: {action.tool}({action.tool_input})")
                    yield {
                        "type": "tool_call", 
                        "tool": action.tool, 
                        "input": action.tool_input,
                        "log": action.log,
                    }

                    
                    # Special Case: Final Answer in ReAct
                    if action.tool == "Final Answer":
                         output = action.tool_input
                         if isinstance(output, dict):
                             if "answer" in output:
                                 output = output["answer"]
                             elif "text" in output:
                                 output = output["text"]
                         yield {"type": "final_answer", "content": str(output)}
                         return

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
                    
            yield {"type": "error", "content": f"Agent exceeded {self.max_steps} steps."}
            raise MaxStepsExceeded(f"Agent exceeded {self.max_steps} steps.")

    def _construct_system_prompt(self, base_prompt: str, tools: List[Tool]) -> str:
        """Inject tool definitions into system prompt."""
        tool_desc = "\n".join([f"- {t.name}: {t.description} (Input: {t.inputSchema})" for t in tools])
        
        react_instructions = """
You have access to the following tools:
{tool_desc}

Use the following format:

Thought: you should always think about what to do
Action: {
  "tool": "tool_name",
  "tool_input": { ... }
}
Observation: the result of the action
... (this Thought/Action/Observation can repeat N times)
Thought: I now know the final answer
Action: {
  "tool": "Final Answer", 
  "tool_input": "the final answer to the original input question"
}

If no tool is needed, just reply with the Final Answer.
""".replace("{tool_desc}", tool_desc)

        return f"{base_prompt}\n\n{react_instructions}"

    def _build_context(self, user_input: str, history: List[AgentStep]) -> str:
        """Concatenate history for ReAct style context."""
        context = f"Question: {user_input}\n"
        
        for step in history:
            # We reconstruct the thought process from the action's log
            context += f"Thought: {step.action.log}\n"
            context += f"Action: {{\n  \"tool\": \"{step.action.tool}\",\n  \"tool_input\": {step.action.tool_input}\n}}\n"
            context += f"Observation: {step.observation}\n" # observation is now a string
        
        context += "Thought:" # Nudge the LLM to continue thinking
        return context
