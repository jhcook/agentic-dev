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
import json
import csv
from io import StringIO
from agent.core.formatters import format_data

SAMPLE_DATA = [
    {"ID": "1", "Title": "Test Item", "State": "ACTIVE"},
    {"ID": "2", "Title": "Another Item", "State": "DRAFT"}
]

EMPTY_DATA = []

INJECTION_DATA = [
    {"ID": "3", "Title": "=SUM(A1:B1)", "State": "@cmd"}
]

def test_format_json():
    result = format_data("json", SAMPLE_DATA)
    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["ID"] == "1"
    assert parsed[0]["Title"] == "Test Item"

def test_format_csv():
    result = format_data("csv", SAMPLE_DATA)
    assert "ID,Title,State" in result
    assert "1,Test Item,ACTIVE" in result
    assert "2,Another Item,DRAFT" in result

def test_format_csv_injection():
    result = format_data("csv", INJECTION_DATA)
    # Check that dangerous characters are escaped with a single quote
    assert "'=SUM(A1:B1)" in result
    assert "'@cmd" in result

def test_format_tsv():
    result = format_data("tsv", SAMPLE_DATA)
    assert "ID\tTitle\tState" in result
    assert "1\tTest Item\tACTIVE" in result

def test_format_yaml():
    result = format_data("yaml", SAMPLE_DATA)
    assert "- ID: '1'" in result
    assert "  Title: Test Item" in result

def test_format_markdown():
    result = format_data("markdown", SAMPLE_DATA)
    assert "| ID | Title | State |" in result
    assert "| --- | --- | --- |" in result
    assert "| 1 | Test Item | ACTIVE |" in result

def test_format_plain():
    result = format_data("plain", SAMPLE_DATA)
    assert "ID\tTitle\tState" in result
    assert "1\tTest Item\tACTIVE" in result

def test_format_pretty():
    # Pretty format returns JSON string fallback for non-console use in the function
    # The actual rendering happens in the command
    result = format_data("pretty", SAMPLE_DATA)
    assert json.loads(result) == SAMPLE_DATA

def test_unsupported_format():
    with pytest.raises(ValueError):
        format_data("invalid_format", SAMPLE_DATA)

def test_empty_data():
    for fmt in ["json", "csv", "yaml", "markdown", "plain", "tsv"]:
        result = format_data(fmt, EMPTY_DATA)
        if fmt == "json":
            assert result == "[]"
        elif fmt == "yaml":
            assert result.strip() == "[]"
        else:
            assert result == ""
