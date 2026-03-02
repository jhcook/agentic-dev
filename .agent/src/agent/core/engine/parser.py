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

import ast
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

        # Strategy 4: YAML-style action (tool: name / tool_input: ...)
        if action_data is None:
            action_data = self._try_yaml_action(text)

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

    def _try_yaml_action(self, text: str) -> dict | None:
        """Parse YAML-style actions that LLMs sometimes produce.

        Handles formats like:
            Action:
              tool: read_file
              tool_input:
                path: .agent/tui/app.py

        Or inline:
            Action:
              tool: read_file
              tool_input: {"path": "app.py"}
        """
        # Look for 'tool:' and 'tool_input:' patterns
        tool_match = re.search(
            r'(?:Action:.*?)?\btool:\s*(["\']?)([\w_]+)\1\s*$',
            text, re.MULTILINE
        )
        if not tool_match:
            return None

        tool_name = tool_match.group(2)

        # Now find tool_input — it could be inline JSON or YAML-style
        input_match = re.search(
            r'tool_input:\s*(.+)',
            text[tool_match.end():], re.DOTALL
        )
        if not input_match:
            return None

        input_text = input_match.group(1).strip()

        # Try parsing as JSON first
        try:
            tool_input = json.loads(input_text.split('\n')[0] if '{' in input_text.split('\n')[0] else input_text)
            return {"tool": tool_name, "tool_input": tool_input}
        except (json.JSONDecodeError, IndexError):
            pass

        # Try ast.literal_eval
        try:
            result = ast.literal_eval(input_text.split('\n')[0] if '{' in input_text.split('\n')[0] else input_text)
            if isinstance(result, dict):
                return {"tool": tool_name, "tool_input": result}
        except (ValueError, SyntaxError):
            pass

        # Parse YAML-style indented key: value pairs
        tool_input = {}
        for line in input_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            kv_match = re.match(r'([\w_]+):\s*(.+)', line)
            if kv_match:
                key = kv_match.group(1)
                val = kv_match.group(2).strip()
                # Strip surrounding quotes
                if (val.startswith('"') and val.endswith('"')) or \
                   (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                # Try to parse booleans/numbers
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.lower() == 'none' or val.lower() == 'null':
                    val = None
                tool_input[key] = val
            else:
                break  # Stop at non-key-value lines

        if tool_input:
            logger.info(f"Parsed YAML-style action: {tool_name}({tool_input})")
            return {"tool": tool_name, "tool_input": tool_input}

        return None

    @staticmethod
    def _extract_json(text: str, start: int) -> dict | None:
        """Extract a JSON object from text starting at `start` using brace counting.

        Handles both strict JSON (double-quoted) and Python dict syntax
        (single-quoted) that LLMs commonly output. Also handles nested
        extra braces (e.g., {{ ... }}).
        """
        # Find the first opening brace
        idx = text.find('{', start)
        if idx < 0:
            return None
            
        depth = 0
        in_string = False
        string_char = None
        escape = False
        first_brace_idx = idx
        
        for i in range(idx, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch in ('"', "'") and not escape:
                if in_string:
                    if ch == string_char:
                        in_string = False
                        string_char = None
                else:
                    in_string = True
                    string_char = ch
                continue
                
            if in_string:
                continue
                
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    raw = text[first_brace_idx:i + 1]
                    
                    # Robust extraction: try parsing 'raw', but if it fails, 
                    # check if it's wrapped in extra braces (like {{...}})
                    # and strip them.
                    candidates = [raw]
                    # If it looks like {{...}}, add stripped version
                    while raw.startswith('{{') and raw.endswith('}}'):
                        raw = raw[1:-1].strip()
                        candidates.append(raw)
                    
                    for candidate in candidates:
                        # Try strict JSON first
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            pass
                        # Fallback: Python dict syntax (single quotes, True/False/None)
                        try:
                            result = ast.literal_eval(candidate)
                            if isinstance(result, dict):
                                return result
                        except (ValueError, SyntaxError, TypeError):
                            pass
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
