import asyncio
import logging
from typing import Any, Dict, List, Optional
import time

from agent.core.ai.service import AIService
from agent.core.engine.parser import BaseParser, ReActJsonParser
from agent.core.engine.typedefs import AgentAction, AgentFinish, AgentStep
from agent.core.mcp.client import MCPClient, Tool
from agent.core.security import SecureManager

logger = logging.getLogger(__name__)

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
        system_prompt: str = "You are a helpful AI assistant."
    ):
        self.llm = llm
        self.mcp = mcp_client
        self.parser = parser or ReActJsonParser()
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.secure_manager = SecureManager() # For scrubbing

    async def run(self, user_prompt: str) -> str:
        """
        Run the agent loop.
        """
        steps_taken = 0
        history: List[AgentStep] = []
        
        # Discover tools first (to inject into prompt)
        try:
             tools = await self.mcp.list_tools()
        except Exception as e:
             logger.error(f"Failed to list tools: {e}")
             tools = []

        # Construct initial system prompt with tool definitions
        full_system_prompt = self._construct_system_prompt(self.system_prompt, tools)
        
        current_input = user_prompt
        
        while steps_taken < self.max_steps:
            steps_taken += 1
            
            # Construct context from history
            # Since AIService.complete() is stateless/single-turn, we must
            # concatenate history into the user_prompt for now.
            # Ideally we'd have a chat history API, but this works for ReAct.
            conversation_context = self._build_context(current_input, history)
            
            # 1. THINK
            logger.info(f"Agent Step {steps_taken}: Thinking...")
            try:
                # We use 'complete' which might be blocking or wrapper. 
                # If AIService.complete is blocking, we wrap in asyncio.to_thread 
                # unless we refactor AIService to be async.
                # Assuming AIService is sync (requests/subprocess based), we defer to thread.
                llm_response = await asyncio.to_thread(
                    self.llm.complete,
                    system_prompt=full_system_prompt,
                    user_prompt=conversation_context
                )
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                return "Error: AI Service failed."
            
            # 2. PARSE
            parsed_result = self.parser.parse(llm_response)
            
            if isinstance(parsed_result, AgentFinish):
                logger.info("Agent decided to Finish.")
                return parsed_result.return_values.get("output", "")
                
            elif isinstance(parsed_result, AgentAction):
                action = parsed_result
                logger.info(f"Agent Action: {action.tool}({action.tool_input})")
                
                # Special Case: Final Answer
                if action.tool == "Final Answer":
                     # Logic: If tool input is string, return it. If dict, return value.
                     output = action.tool_input
                     if isinstance(output, dict):
                         # Try to find a reasonable key
                         if "answer" in output: output = output["answer"]
                         elif "text" in output: output = output["text"]
                         # Else return raw dict str
                     return str(output)

                # 3. ACT
                observation_str = ""
                try:
                    tool_result = await self.mcp.call_tool(action.tool, action.tool_input)
                    
                    # Convert result to string (MCP returns object or dict)
                    # We need to handle complex objects
                    output_data = tool_result.content if hasattr(tool_result, 'content') else str(tool_result)
                    observation_str = str(output_data)
                    
                except Exception as e:
                    logger.error(f"Tool Execution Error: {e}")
                    observation_str = f"Error executing tool {action.tool}: {e}"
                
                # 4. OBSERVE (and Scrub!)
                # Security Check: Scrub observation
                scrubbed_observation = self.secure_manager.scrub(observation_str)
                
                step = AgentStep(
                    action=action,
                    observation=scrubbed_observation # Store string directly in observation for now
                )
                history.append(step)
                
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
            context += f"Thought: {step.action.log}\n"
            context += f"Action: {{\n  \"tool\": \"{step.action.tool}\",\n  \"tool_input\": {step.action.tool_input}\n}}\n"
            context += f"Observation: {step.observation.output if hasattr(step.observation, 'output') else step.observation}\n"
        
        context += "Thought:" # Nudge the LLM to continue thinking
        return context

