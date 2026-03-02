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

    def test_code_fence_empty_json(self):
        """Empty code fence should be warned and ignored, falling back to Finish."""
        parser = ReActJsonParser()
        llm_output = "Thought: I have no tools to run.\n\n```json\n\n```"
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish)



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


class TestParserSingleQuoteFallback:
    """Tests for ast.literal_eval fallback when LLMs emit Python dict syntax.

    EXC-004: LLMs (particularly Gemini) frequently emit tool_input with
    single-quoted keys/values. json.loads() rejects these, so the parser
    falls back to ast.literal_eval which safely handles Python literals.
    """

    def test_single_quoted_action(self):
        """Single-quoted dict from LLM should be parsed via ast.literal_eval."""
        parser = ReActJsonParser()
        llm_output = (
            "Thought: I need to read the file.\n"
            "Action: {\n"
            "  'tool': 'read_file',\n"
            "  'tool_input': {'path': 'README.md'}\n"
            "}"
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "read_file"
        assert result.tool_input == {"path": "README.md"}

    def test_python_booleans_in_tool_input(self):
        """Python True/False/None should be handled by ast.literal_eval."""
        parser = ReActJsonParser()
        llm_output = (
            "Action: {\n"
            "  'tool': 'edit_file',\n"
            "  'tool_input': {'path': 'x.py', 'create': True, 'backup': False, 'meta': None}\n"
            "}"
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "edit_file"
        assert result.tool_input["create"] is True
        assert result.tool_input["backup"] is False
        assert result.tool_input["meta"] is None

    def test_nested_single_quoted_input(self):
        """Nested single-quoted dicts should be parsed correctly."""
        parser = ReActJsonParser()
        llm_output = (
            "Thought: Running a command.\n"
            "Action: {'tool': 'run_command', 'tool_input': {'command': 'uv run pytest', 'opts': {'verbose': True}}}"
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "run_command"
        assert result.tool_input["opts"]["verbose"] is True

    def test_extract_json_single_quotes(self):
        """_extract_json should handle single-quoted strings via fallback."""
        text = "{'tool': 'test', 'tool_input': {'key': 'value'}}"
        result = ReActJsonParser._extract_json(text, 0)
        assert result is not None
        assert result["tool"] == "test"
        assert result["tool_input"]["key"] == "value"

    def test_single_quoted_brace_counting(self):
        """Brace counting should handle single-quoted strings correctly."""
        text = "{'tool': 'test', 'tool_input': {'msg': 'use {brackets} here'}}"
        result = ReActJsonParser._extract_json(text, 0)
        assert result is not None
        assert result["tool_input"]["msg"] == "use {brackets} here"

    def test_double_quoted_json_still_preferred(self):
        """Standard double-quoted JSON should still work (json.loads path)."""
        parser = ReActJsonParser()
        llm_output = 'Action: {"tool": "read_file", "tool_input": {"path": "test.py"}}'
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "read_file"
        assert result.tool_input == {"path": "test.py"}


class TestParserYamlFallback:
    """Tests for YAML-style action parsing (Strategy 4).

    LLMs sometimes emit tool calls in YAML format instead of JSON.
    The parser should handle these gracefully.
    """

    def test_yaml_indented_action(self):
        """YAML-style indented key: value pairs."""
        parser = ReActJsonParser()
        llm_output = (
            "Thought: I need to read the file.\n"
            "Action:\n"
            "  tool: read_file\n"
            "  tool_input:\n"
            "    path: .agent/tui/app.py\n"
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "read_file"
        assert result.tool_input["path"] == ".agent/tui/app.py"

    def test_yaml_with_inline_json_input(self):
        """YAML tool name with JSON tool_input."""
        parser = ReActJsonParser()
        llm_output = (
            "Thought: Running command.\n"
            "Action:\n"
            '  tool: run_command\n'
            '  tool_input: {"command": "ls -la"}\n'
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "run_command"
        assert result.tool_input["command"] == "ls -la"

    def test_yaml_quoted_values(self):
        """YAML with quoted string values."""
        parser = ReActJsonParser()
        llm_output = (
            "Action:\n"
            '  tool: read_file\n'
            '  tool_input:\n'
            '    path: "README.md"\n'
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction)
        assert result.tool == "read_file"
        assert result.tool_input["path"] == "README.md"

    def test_real_session_stall_format(self):
        """Reproduce the exact format from the stalling session transcript."""
        parser = ReActJsonParser()
        llm_output = (
            "The user is asking for a status update. My previous action was "
            "to read `.agent/tui/app.py` to add a `/clear-history` command.\n"
            "Action:\n"
            "  tool: read_file\n"
            "  tool_input:\n"
            "    path: .agent/tui/app.py\n"
        )
        result = parser.parse(llm_output)
        assert isinstance(result, AgentAction), (
            f"Expected AgentAction but got AgentFinish: {result}"
        )
        assert result.tool == "read_file"
        assert result.tool_input["path"] == ".agent/tui/app.py"

