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

import pytest
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
        # Should fallback to Finish if json is broken (or handle gracefully)
        # Current implementation falls back to AgentFinish if json load fails
        parser = ReActJsonParser()
        llm_output = 'Action: { "tool": "broken" ' # Missing brace
        
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish) 
        assert "broken" in result.log

    def test_parse_finish_no_action(self):
        parser = ReActJsonParser()
        llm_output = "I know the answer now. It is 42."
        
        result = parser.parse(llm_output)
        assert isinstance(result, AgentFinish)
        assert result.return_values["output"] == llm_output
