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

"""Tests for the formatters module."""

import pytest
import json
import yaml
from agent.core.formatters import (
    format_data,
    format_json,
    format_csv,
    format_yaml,
    format_markdown,
    format_plain,
    format_tsv,
)


# Sample test data
SAMPLE_DATA = [
    {"id": "TEST-001", "title": "Test Story", "state": "DRAFT"},
    {"id": "TEST-002", "title": "Another Story", "state": "COMMITTED"},
]

EMPTY_DATA = []

CSV_INJECTION_DATA = [
    {"id": "TEST-003", "formula": "=SUM(A1:A10)", "state": "DRAFT"},
    {"id": "TEST-004", "formula": "+1+1", "state": "COMMITTED"},
]


class TestFormatData:
    """Tests for the format_data dispatcher function."""
    
    def test_format_data_json(self):
        """Test routing to JSON formatter."""
        result = format_data("json", SAMPLE_DATA)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "TEST-001"
    
    def test_format_data_csv(self):
        """Test routing to CSV formatter."""
        result = format_data("csv", SAMPLE_DATA)
        assert "id,title,state" in result
        assert "TEST-001" in result
    
    def test_format_data_yaml(self):
        """Test routing to YAML formatter."""
        result = format_data("yaml", SAMPLE_DATA)
        parsed = yaml.safe_load(result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "TEST-001"
    
    def test_format_data_markdown(self):
        """Test routing to Markdown formatter."""
        result = format_data("markdown", SAMPLE_DATA)
        assert "| id |" in result
        assert "| --- |" in result
        assert "| TEST-001 |" in result
    
    def test_format_data_plain(self):
        """Test routing to plain text formatter."""
        result = format_data("plain", SAMPLE_DATA)
        lines = result.split("\n")
        assert "id\ttitle\tstate" in lines[0]
        assert "TEST-001" in lines[1]
    
    def test_format_data_tsv(self):
        """Test routing to TSV formatter."""
        result = format_data("tsv", SAMPLE_DATA)
        assert "id\ttitle\tstate" in result
        assert "TEST-001" in result
    
    def test_format_data_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            format_data("invalid_format", SAMPLE_DATA)
        assert "Unsupported format" in str(exc_info.value)
        assert "invalid_format" in str(exc_info.value)


class TestFormatJSON:
    """Tests for JSON formatter."""
    
    def test_format_json_basic(self):
        """Test basic JSON formatting."""
        result = format_json(SAMPLE_DATA)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "TEST-001"
        assert parsed[1]["state"] == "COMMITTED"
    
    def test_format_json_empty(self):
        """Test JSON formatting with empty data."""
        result = format_json(EMPTY_DATA)
        parsed = json.loads(result)
        assert parsed == []
    
    def test_format_json_unicode(self):
        """Test JSON formatting with Unicode characters."""
        data = [{"id": "TEST", "title": "Café ☕"}]
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed[0]["title"] == "Café ☕"


class TestFormatCSV:
    """Tests for CSV formatter."""
    
    def test_format_csv_basic(self):
        """Test basic CSV formatting."""
        result = format_csv(SAMPLE_DATA)
        lines = result.replace('\r', '').strip().split("\n")
        assert lines[0] == "id,title,state"
        assert "TEST-001,Test Story,DRAFT" in lines[1]
    
    def test_format_csv_empty(self):
        """Test CSV formatting with empty data."""
        result = format_csv(EMPTY_DATA)
        assert result == ""
    
    def test_format_csv_injection_prevention(self):
        """Test that CSV injection is prevented by escaping formulas."""
        result = format_csv(CSV_INJECTION_DATA)
        lines = result.split("\n")
        # Formulas should be escaped with a leading quote
        assert "'=SUM(A1:A10)" in result
        assert "'+1+1" in result


class TestFormatYAML:
    """Tests for YAML formatter."""
    
    def test_format_yaml_basic(self):
        """Test basic YAML formatting."""
        result = format_yaml(SAMPLE_DATA)
        parsed = yaml.safe_load(result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "TEST-001"
    
    def test_format_yaml_empty(self):
        """Test YAML formatting with empty data."""
        result = format_yaml(EMPTY_DATA)
        parsed = yaml.safe_load(result)
        assert parsed == []


class TestFormatMarkdown:
    """Tests for Markdown formatter."""
    
    def test_format_markdown_basic(self):
        """Test basic Markdown table formatting."""
        result = format_markdown(SAMPLE_DATA)
        lines = result.split("\n")
        assert "| id | title | state |" in lines[0]
        assert "| --- | --- | --- |" in lines[1]
        assert "| TEST-001 | Test Story | DRAFT |" in lines[2]
    
    def test_format_markdown_empty(self):
        """Test Markdown formatting with empty data."""
        result = format_markdown(EMPTY_DATA)
        assert result == ""
    
    def test_format_markdown_pipe_escaping(self):
        """Test that pipe characters in values are escaped."""
        data = [{"id": "TEST", "title": "Pipe | Character"}]
        result = format_markdown(data)
        assert "Pipe \\| Character" in result


class TestFormatPlain:
    """Tests for plain text formatter."""
    
    def test_format_plain_basic(self):
        """Test basic plain text formatting with tabs."""
        result = format_plain(SAMPLE_DATA)
        lines = result.split("\n")
        assert lines[0] == "id\ttitle\tstate"
        assert "TEST-001\tTest Story\tDRAFT" in lines[1]
    
    def test_format_plain_empty(self):
        """Test plain text formatting with empty data."""
        result = format_plain(EMPTY_DATA)
        assert result == ""


class TestFormatTSV:
    """Tests for TSV formatter."""
    
    def test_format_tsv_basic(self):
        """Test basic TSV formatting."""
        result = format_tsv(SAMPLE_DATA)
        lines = result.strip().split("\n")
        assert "id\ttitle\tstate" in lines[0]
        assert "TEST-001" in result
    
    def test_format_tsv_empty(self):
        """Test TSV formatting with empty data."""
        result = format_tsv(EMPTY_DATA)
        assert result == ""
    
    def test_format_tsv_injection_prevention(self):
        """Test that TSV injection is prevented by escaping formulas."""
        result = format_tsv(CSV_INJECTION_DATA)
        # Formulas should be escaped with a leading quote
        assert "'=SUM(A1:A10)" in result
        assert "'+1+1" in result
