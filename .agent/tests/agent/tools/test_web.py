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
Unit tests for the web tool domain.
"""

import pytest
import httpx
from unittest.mock import patch, MagicMock
from agent.tools.web import fetch_url, read_docs

import requests

@patch("agent.tools.web.fetch_with_resource_guards")
def test_fetch_url_success(mock_fetch):
    """Verify successful fetch and markdown conversion."""
    mock_fetch.return_value = b"<h1>Hello</h1><p>World</p>"

    result = fetch_url("https://example.com")
    
    assert result["success"] is True
    assert "# Hello" in result["output"]
    assert "World" in result["output"]

@patch("agent.tools.web.fetch_with_resource_guards")
def test_fetch_url_timeout(mock_fetch):
    """Verify timeout handling (Negative Test)."""
    mock_fetch.side_effect = requests.RequestException("Timed out")

    result = fetch_url("https://slow.com")
    
    assert result["success"] is False
    assert "Timed out" in result["error"]

@patch("agent.tools.web.fetch_with_resource_guards")
def test_fetch_url_max_size(mock_fetch):
    """Verify max payload size enforcement."""
    mock_fetch.side_effect = ValueError("Security Violation: Response size exceeded")

    result = fetch_url("https://huge-file.com")
    
    assert result["success"] is False
    assert "Security Violation" in result["error"]

@patch("agent.tools.web.fetch_url")
def test_read_docs_passthrough(mock_fetch):
    """Verify read_docs correctly delegates to fetch_url."""
    mock_fetch.return_value = {"success": True, "output": "docs content"}
    
    result = read_docs("https://docs.example.com")
    assert result["output"] == "docs content"
    mock_fetch.assert_called_once_with("https://docs.example.com")
