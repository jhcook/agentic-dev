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
