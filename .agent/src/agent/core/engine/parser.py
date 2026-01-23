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
from abc import ABC, abstractmethod
from typing import Union

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
        
        # Look for Action JSON block
        # We look for a JSON object with "tool" and "tool_input" keys
        # Simple regex to find the *last* json-like block might be risky, 
        # so let's try to find an explicit "Action:" marker explicitly or 
        # just look for the json pattern. 
        
        # Pattern: Action:\s*(\{.*\})
        action_pattern = r"(?s)Action:\s*(\{.*\})"
        match = re.search(action_pattern, text)
        
        if match:
            try:
                action_json_str = match.group(1)
                # Attempt to parse
                # Handle potentially malformed json (e.g. single quotes)
                # For MVP, rely on strict json, maybe relax later
                action_data = json.loads(action_json_str)
                
                tool = action_data.get("tool")
                tool_input = action_data.get("tool_input")
                
                if tool and tool_input is not None:
                    return AgentAction(
                        tool=tool,
                        tool_input=tool_input,
                        log=text[:match.start()].strip()
                    )
            except json.JSONDecodeError:
                # If invalid json, treat as Hallucination or Finish? 
                # Better to fail safely or treat as finish.
                # Let's treat as Finish but log warning in real app.
                pass
                
        # If no action found, it's a Finish
        return AgentFinish(
            return_values={"output": text},
            log=text
        )

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
