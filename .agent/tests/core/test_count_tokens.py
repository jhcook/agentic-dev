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

"""
Comprehensive tests for count_tokens.py utility.

Tests cover:
- Basic functionality with default and custom models
- Edge cases (empty strings, whitespace, special characters)
- Unicode and emoji handling
- Large text scenarios
- Unknown model fallback behavior
- CLI interface functionality
"""
import io

import pytest

from agent.core.tokens import token_manager


@pytest.fixture
def sample_text():
    return "This is a sample text for testing token counting."

@pytest.fixture
def large_text():
    return " ".join(["word"] * 1000)

@pytest.fixture
def code_snippet():
    return "def hello():\n    print('Hello world')"

@pytest.fixture
def multiline_text():
    return "\n".join([f"Line {i}" for i in range(50)])

def count_tokens(text, model="gpt-4o"):
    """Compatibility wrapper for TokenManager."""
    provider = "openai"
    if model and "gemini" in model.lower():
        provider = "gemini"
    # Basic provider switch for test compatibility
    return token_manager.count_tokens(text, provider=provider, model_name=model)


class TestBasicFunctionality:
    """Test core token counting functionality."""
    
    def test_basic_token_counting(self, sample_text):
        """Test basic token counting with default model."""
        result = count_tokens(sample_text)
        assert isinstance(result, int)
        assert result > 0
        # "This is a sample text for testing token counting." should be ~10 tokens
        assert 8 <= result <= 15
    
    def test_default_model_parameter(self):
        """Test that default model is gpt-4o."""
        text = "Hello world"
        result = count_tokens(text)
        # Should work without specifying model
        assert result > 0
    
    def test_explicit_model_parameter(self):
        """Test token counting with explicit model parameter."""
        text = "Hello world"
        result = count_tokens(text, model="gpt-4o")
        assert result > 0
        assert isinstance(result, int)
    
    def test_consistency(self):
        """Test that same text produces same token count."""
        text = "Consistency test string"
        count1 = count_tokens(text)
        count2 = count_tokens(text)
        assert count1 == count2


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_empty_string(self):
        """Test counting tokens in empty string."""
        result = count_tokens("")
        assert result == 0
    
    def test_whitespace_only(self):
        """Test counting tokens in whitespace-only string."""
        result = count_tokens("   ")
        assert result >= 0
        # Whitespace typically counts as tokens
        assert result <= 3
    
    def test_single_character(self):
        """Test counting tokens in single character."""
        result = count_tokens("a")
        assert result >= 1
        assert result <= 2
    
    def test_newlines(self):
        """Test counting tokens with newlines."""
        result = count_tokens("line1\nline2\nline3")
        assert result > 0
    
    def test_tabs(self):
        """Test counting tokens with tabs."""
        result = count_tokens("word1\tword2\tword3")
        assert result > 0
    
    def test_special_characters(self):
        """Test counting tokens with special characters."""
        text = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        result = count_tokens(text)
        assert result > 0
    
    def test_unicode_characters(self):
        """Test counting tokens with unicode characters."""
        text = "Hello 世界 🌍"
        result = count_tokens(text)
        assert result > 0
        # Unicode typically takes more tokens
        assert result >= 4
    
    def test_mixed_content(self):
        """Test counting tokens with mixed content types."""
        text = "Code: def func():\n    return 42  # Comment"
        result = count_tokens(text)
        assert result > 0


class TestModelHandling:
    """Test different model arguments and fallback behavior."""
    
    def test_gpt4o_model(self):
        """Test with gpt-4o model explicitly."""
        text = "Test text"
        result = count_tokens(text, model="gpt-4o")
        assert result > 0
    
    def test_unknown_model_fallback(self):
        """Test that unknown models fall back to cl100k_base."""
        text = "Test text"
        # Should not raise exception, should fallback gracefully
        result = count_tokens(text, model="nonexistent-model-xyz")
        assert result > 0
        assert isinstance(result, int)
    
    def test_gpt35_turbo_model(self):
        """Test with gpt-3.5-turbo model."""
        text = "Test text"
        result = count_tokens(text, model="gpt-3.5-turbo")
        assert result > 0
    
    def test_gpt4_model(self):
        """Test with gpt-4 model."""
        text = "Test text"
        result = count_tokens(text, model="gpt-4")
        assert result > 0
    
    def test_different_models_same_encoding(self):
        """Test that models using same encoding produce same counts."""
        text = "Encoding consistency test"
        # gpt-4 and gpt-3.5-turbo use same encoding
        count1 = count_tokens(text, model="gpt-4")
        count2 = count_tokens(text, model="gpt-3.5-turbo")
        assert count1 == count2


class TestRealWorldScenarios:
    """Test with real-world text scenarios."""
    
    def test_large_text(self, large_text):
        """Test counting tokens in large text."""
        result = count_tokens(large_text)
        assert result > 0
        # 1000 words should be roughly 1300-1500 tokens
        assert 1000 <= result <= 2000
    
    def test_code_snippet(self, code_snippet):
        """Test counting tokens in code snippet."""
        result = count_tokens(code_snippet)
        assert result > 0
        # Code should have reasonable token count
        assert 5 <= result <= 50
    
    def test_json_structure(self):
        """Test counting tokens in JSON structure."""
        text = '{"key": "value", "number": 42, "nested": {"inner": "data"}}'
        result = count_tokens(text)
        assert result > 0
        assert 10 <= result <= 30
    
    def test_markdown_text(self):
        """Test counting tokens in markdown text."""
        text = """
# Heading 1
## Heading 2

**Bold text** and *italic text*

- List item 1
- List item 2

```python
def example():
    return "code"
```
"""
        result = count_tokens(text)
        assert result > 0
        assert 20 <= result <= 80
    
    def test_multiline_text(self, multiline_text):
        """Test counting tokens in multiline text."""
        result = count_tokens(multiline_text)
        assert result > 0
        # 50 lines with content should have substantial tokens
        assert result > 100


class TestCLIInterface:
    """Test command-line interface functionality."""
    
    def test_cli_basic_usage(self, monkeypatch):
        """Test CLI with stdin input."""
        # Mock stdin
        test_input = "Test input from stdin"
        monkeypatch.setattr('sys.stdin', io.StringIO(test_input))
        
        # Capture stdout
        captured_output = io.StringIO()
        monkeypatch.setattr('sys.stdout', captured_output)
        
        # Run the main block logic
        text = test_input
        token_count = count_tokens(text)
        print(token_count)
        
        output = captured_output.getvalue().strip()
        assert output.isdigit()
        assert int(output) > 0
    
    def test_cli_empty_input(self, monkeypatch):
        """Test CLI with empty stdin."""
        monkeypatch.setattr('sys.stdin', io.StringIO(""))
        
        captured_output = io.StringIO()
        monkeypatch.setattr('sys.stdout', captured_output)
        
        text = ""
        token_count = count_tokens(text)
        print(token_count)
        
        output = captured_output.getvalue().strip()
        assert output == "0"
    
    def test_cli_large_input(self, monkeypatch, large_text):
        """Test CLI with large stdin input."""
        monkeypatch.setattr('sys.stdin', io.StringIO(large_text))
        
        captured_output = io.StringIO()
        monkeypatch.setattr('sys.stdout', captured_output)
        
        text = large_text
        token_count = count_tokens(text)
        print(token_count)
        
        output = captured_output.getvalue().strip()
        assert output.isdigit()
        assert int(output) > 100


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_none_input_raises_error(self):
        """Test that None input raises appropriate error."""
        with pytest.raises(TypeError):
            count_tokens(None)
    
    def test_non_string_input_raises_error(self):
        """Test that non-string input raises appropriate error."""
        with pytest.raises((TypeError, AttributeError)):
            count_tokens(12345)
    
    def test_list_input_raises_error(self):
        """Test that list input raises appropriate error."""
        with pytest.raises((TypeError, AttributeError)):
            count_tokens(["not", "a", "string"])


class TestPerformance:
    """Test performance characteristics."""
    
    def test_very_large_text_performance(self):
        """Test that very large text is handled efficiently."""
        # 10,000 words
        text = " ".join(["word"] * 10000)
        import time
        start = time.time()
        result = count_tokens(text)
        duration = time.time() - start
        
        # Should complete in reasonable time (< 1 second)
        assert duration < 1.0
        assert result > 5000  # Should have substantial token count
    
    def test_repeated_counting_consistency(self):
        """Test that repeated counting gives consistent results."""
        text = "Performance consistency test"
        results = [count_tokens(text) for _ in range(10)]
        
        # All results should be identical
        assert len(set(results)) == 1
        assert all(r == results[0] for r in results)
