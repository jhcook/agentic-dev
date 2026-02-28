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

import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Union

logger = logging.getLogger(__name__)

from agent.core.engine.typedefs import AgentAction, AgentFinish

class BaseParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        pass

class ReActJsonParser(BaseParser):
    """
    Parses LLM output expecting a JSON structure for Actions.
    Fallback to Finish if no action detected.
    
    Expected format:
    Thought: ...
    Action: {
      "tool": "tool_name",
      "tool_input": { ... }
    }
    """
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        # Clean text
        text = text.strip()

        # Strategy 1: Look for Action: followed by JSON (non-greedy)
        action_data = self._try_action_marker(text)

        # Strategy 2: Look for JSON inside markdown code fences
        if action_data is None:
            action_data = self._try_code_fence(text)

        # Strategy 3: Find any JSON block with "tool" key
        if action_data is None:
            action_data = self._try_any_json_block(text)

        if action_data:
            tool = action_data.get("tool")
            tool_input = action_data.get("tool_input")
            if tool and tool_input is not None:
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
        # Attempt to extract text between Thought: and Final Answer: if both exist
        if re.search(r"Thought:.*Final Answer:", output, re.DOTALL | re.IGNORECASE):
            output = re.sub(r"^Thought:.*?Final Answer:\s*", "", output, flags=re.DOTALL | re.IGNORECASE)
        
        output = re.sub(r"^(Final Answer:|Thought:)\s*", "", output, flags=re.IGNORECASE | re.MULTILINE).strip()

        return AgentFinish(
            return_values={"output": output},
            log=output  # Use cleaned output as log to prevent raw leakage
        )

    def _try_action_marker(self, text: str) -> dict | None:
        """Try to extract JSON after 'Action:' marker."""
        # Find all 'Action:' positions and try to parse JSON after each
        for match in re.finditer(r"Action:\s*", text):
            result = self._extract_json(text, match.end())
            if result and "tool" in result:
                return result
        return None

    def _try_code_fence(self, text: str) -> dict | None:
        """Try to extract JSON from markdown code fences."""
        fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        for match in re.finditer(fence_pattern, text):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "tool" in data:
                    return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode JSON from code fence: {e}")
                continue
        return None

    def _try_any_json_block(self, text: str) -> dict | None:
        """Last resort: find any JSON object with a 'tool' key."""
        for i, ch in enumerate(text):
            if ch == '{':
                data = self._extract_json(text, i)
                if data and "tool" in data and "tool_input" in data:
                    return data
        return None

    @staticmethod
    def _extract_json(text: str, start: int) -> dict | None:
        """Extract a JSON object from text starting at `start` using brace counting."""
        # Find the opening brace
        idx = text.find('{', start)
        if idx < 0:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(idx, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[idx:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

class ReActRegexParser(BaseParser):
    """
    Parses output in the classic format:
    Action: tool_name
    Action Input: tool_input_string
    """
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        action_pattern = r"Action:\s*(.*?)\n"
        input_pattern = r"Action Input:\s*(.*)"
        
        action_match = re.search(action_pattern, text)
        input_match = re.search(input_pattern, text, re.DOTALL)
        
        if action_match and input_match:
            tool = action_match.group(1).strip()
            tool_input_str = input_match.group(1).strip()
            
            # Try to parse input as json, else string
            try:
                tool_input = json.loads(tool_input_str)
            except json.JSONDecodeError:
                tool_input = {"input": tool_input_str}
            
            return AgentAction(
                tool=tool,
                tool_input=tool_input,
                log=text.split("Action:")[0].strip()
            )
            
        return AgentFinish(
            return_values={"output": text},
            log=text
        )
