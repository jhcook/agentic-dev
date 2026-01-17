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

"""Tests for text utilities."""

import pytest
from agent.utils.text import sanitize_mermaid_label


class TestSanitizeMermaidLabel:
    """Tests for sanitize_mermaid_label function."""

    def test_simple_string(self):
        """Test with a simple string containing no special characters."""
        result = sanitize_mermaid_label("Simple text")
        assert result == "Simple text"

    def test_empty_string(self):
        """Test with an empty string."""
        result = sanitize_mermaid_label("")
        assert result == ""

    def test_none_returns_empty(self):
        """Test that None-like input returns empty string."""
        result = sanitize_mermaid_label("")
        assert result == ""

    def test_double_quotes(self):
        """Test escaping of double quotes."""
        result = sanitize_mermaid_label('Text with "quotes"')
        assert result == 'Text with #quot;quotes#quot;'

    def test_angle_brackets(self):
        """Test escaping of angle brackets."""
        result = sanitize_mermaid_label("<script>alert</script>")
        assert result == "#lt;script#gt;alert#lt;/script#gt;"

    def test_pipe_character(self):
        """Test escaping of pipe character used for node shapes."""
        result = sanitize_mermaid_label("Choice A | Choice B")
        assert result == "Choice A #124; Choice B"

    def test_mixed_special_characters(self):
        """Test with multiple types of special characters."""
        result = sanitize_mermaid_label('Node "A" <-> Node |B|')
        assert "#quot;" in result
        assert "#lt;" in result
        assert "#gt;" in result
        assert "#124;" in result

    def test_unicode_preserved(self):
        """Test that unicode characters are preserved."""
        result = sanitize_mermaid_label("こんにちは 🚀")
        assert result == "こんにちは 🚀"

    def test_newlines_preserved(self):
        """Test that newlines are preserved (Mermaid handles these in labels)."""
        result = sanitize_mermaid_label("Line 1\nLine 2")
        assert result == "Line 1\nLine 2"
