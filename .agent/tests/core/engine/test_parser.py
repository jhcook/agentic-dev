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

"""Tests for ReActJsonParser — comprehensive coverage of all 3 extraction
strategies and the brace-counting _extract_json helper."""

from agent.core.engine.parser import ReActJsonParser
from agent.core.engine.typedefs import AgentAction, AgentFinish


class TestReActJsonParser:

    def test_parse_valid_action(self):
        parser = ReActJsonParser()
        llm_output = """
        Thought: I need to check the weather.
        Action: {
            "tool": "get_weather",
            "tool_input": {"location": "London"}
        }
        """
        result = parser.parse(llm_output)

        assert isinstance(result, AgentAction)
        assert result.tool == "get_weather"
        assert result.tool_input == {"location": "London"}
        assert "I need to check the weather" in result.log

    def test_parse_malformed_json(self):
        """Malformed JSON falls back to AgentFinish."""
        parser = ReActJsonParser()
        llm_output = 'Action: { "tool": "broken" '  # Missing brace
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish)
        assert "broken" in result.log

    def test_parse_finish_no_action(self):
        parser = ReActJsonParser()
        llm_output = "I know the answer now. It is 42."
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish)
        assert result.return_values["output"] == llm_output


class TestParserCodeFenceStrategy:
    """Tests for Strategy 2: JSON inside markdown code fences."""

    def test_code_fence_json(self):
        parser = ReActJsonParser()
        llm_output = """Thought: I'll search for it.

```json
{
  "tool": "search_codebase",
  "tool_input": {"pattern": "def main"}
}
```
"""
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "search_codebase"
        assert result.tool_input == {"pattern": "def main"}

    def test_code_fence_no_lang(self):
        """Code fence without 'json' language tag should still work."""
        parser = ReActJsonParser()
        llm_output = """Thought: Running the command.

```
{"tool": "run_command", "tool_input": {"command": "ls -la"}}
```
"""
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "run_command"


class TestParserNestedJSON:
    """Tests for correct handling of nested JSON objects via brace-counting."""

    def test_deeply_nested_tool_input(self):
        parser = ReActJsonParser()
        llm_output = """Thought: I need to edit the file.
Action: {
    "tool": "edit_file",
    "tool_input": {
        "path": "/tmp/test.py",
        "content": "def hello():\\n    return True",
        "options": {"create": true, "backup": false}
    }
}"""
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "edit_file"
        assert result.tool_input["path"] == "/tmp/test.py"
        assert result.tool_input["options"]["create"] is True

    def test_single_line_nested(self):
        """Compact JSON with nested objects on a single line."""
        parser = ReActJsonParser()
        llm_output = 'Action: {"tool": "search", "tool_input": {"query": "foo", "opts": {"case": true}}}'
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "search"
        assert result.tool_input["opts"]["case"] is True


class TestParserAnyJSONStrategy:
    """Tests for Strategy 3: find any JSON block with 'tool' key."""

    def test_json_without_action_marker(self):
        """JSON with tool/tool_input but no 'Action:' prefix should be found."""
        parser = ReActJsonParser()
        llm_output = """Thought: Let me read the file.
I'll use this:
{"tool": "read_file", "tool_input": {"path": "/tmp/x.py"}}
"""
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "read_file"

    def test_json_without_tool_key_is_finish(self):
        """JSON without 'tool' key should be treated as finish."""
        parser = ReActJsonParser()
        llm_output = '{"answer": "42", "confidence": "high"}'
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish)


class TestParserFinalAnswer:
    """Tests for the Final Answer action shortcut."""

    def test_final_answer_string(self):
        parser = ReActJsonParser()
        llm_output = 'Action: {"tool": "Final Answer", "tool_input": "The answer is 42"}'
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "Final Answer"
        assert result.tool_input == "The answer is 42"

    def test_final_answer_dict(self):
        parser = ReActJsonParser()
        llm_output = 'Action: {"tool": "Final Answer", "tool_input": {"answer": "done", "summary": "all good"}}'
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "Final Answer"
        assert result.tool_input["answer"] == "done"


class TestExtractJSON:
    """Direct tests for the _extract_json static method."""

    def test_simple_object(self):
        result = ReActJsonParser._extract_json('hello {"a": 1} world', 0)
        assert result == {"a": 1}

    def test_nested_object(self):
        text = '{"outer": {"inner": {"deep": true}}}'
        result = ReActJsonParser._extract_json(text, 0)
        assert result["outer"]["inner"]["deep"] is True

    def test_string_with_braces(self):
        """Braces inside strings should not confuse the parser."""
        text = '{"tool": "test", "tool_input": {"msg": "use {brackets} here"}}'
        result = ReActJsonParser._extract_json(text, 0)
        assert result["tool_input"]["msg"] == "use {brackets} here"

    def test_no_json_returns_none(self):
        result = ReActJsonParser._extract_json("no json here", 0)
        assert result is None

    def test_start_offset(self):
        text = 'ignored {"a": 1} target {"b": 2}'
        result = ReActJsonParser._extract_json(text, 18)
        assert result == {"b": 2}

    def test_escaped_quotes_in_string(self):
        text = '{"tool": "test", "tool_input": {"msg": "say \\"hello\\""}}'
        result = ReActJsonParser._extract_json(text, 0)
        assert result is not None
        assert result["tool"] == "test"
