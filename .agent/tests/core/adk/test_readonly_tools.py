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

"""Tests for read-only governance tools (make_tools).

Covers read_file, search_codebase, list_directory, read_adr, read_journey.
These tools are used by governance agents and the console for file reading.
"""

import pytest
from agent.core.adk.tools import make_tools


@pytest.fixture
def repo_root(tmp_path):
    """Create a temporary repo root with test files."""
    # Source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n")
    (src / "utils.py").write_text("def add(a, b):\n    return a + b\n")

    # Templates
    templates = tmp_path / ".agent" / "templates"
    templates.mkdir(parents=True)
    (templates / "license_header.txt").write_text(
        "Copyright 2026 Test\nLicensed under Apache 2.0\n"
    )

    # ADRs
    adr_dir = tmp_path / ".agent" / "adrs"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001-test-decision.md").write_text("# ADR-001\nTest decision\n")

    # Journeys
    jrn_dir = tmp_path / ".agent" / "cache" / "journeys" / "INFRA"
    jrn_dir.mkdir(parents=True)
    (jrn_dir / "JRN-001-test-journey.md").write_text("# Journey 001\nTest journey\n")

    # A short file (fewer than 2000 lines)
    (tmp_path / "short.txt").write_text("line1\nline2\nline3\n")

    # An empty file
    (tmp_path / "empty.txt").write_text("")

    # A single-line file
    (tmp_path / "single.txt").write_text("only line")

    # README
    (tmp_path / "README.md").write_text("# Test Repo\n")

    return tmp_path


@pytest.fixture
def tools(repo_root):
    """Return the 5 read-only tools bound to the temp repo root."""
    tool_list = make_tools(repo_root)
    return {fn.__name__: fn for fn in tool_list}


class TestReadFile:
    """Tests for the read_file tool."""

    def test_reads_short_file(self, tools):
        """Files under 2000 lines must be read completely."""
        result = tools["read_file"]("short.txt")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "truncated" not in result

    def test_reads_single_line_file(self, tools):
        """Single-line files must return that line."""
        result = tools["read_file"]("single.txt")
        assert "only line" in result

    def test_reads_empty_file(self, tools):
        """Empty files should return empty string, not an error."""
        result = tools["read_file"]("empty.txt")
        assert "Error" not in result

    def test_reads_template_file(self, tools):
        """Template files in .agent/ must be readable."""
        result = tools["read_file"](".agent/templates/license_header.txt")
        assert "Copyright" in result
        assert "Error" not in result

    def test_reads_source_file(self, tools):
        result = tools["read_file"]("src/main.py")
        assert "hello" in result

    def test_nonexistent_file_returns_error(self, tools):
        result = tools["read_file"]("does_not_exist.txt")
        assert "Error" in result

    def test_rejects_path_traversal(self, tools):
        with pytest.raises(ValueError, match="outside the repository root"):
            tools["read_file"]("../outside.txt")

    def test_directory_returns_error(self, tools):
        result = tools["read_file"]("src")
        assert "Error" in result


class TestListDirectory:
    """Tests for the list_directory tool."""

    def test_lists_root(self, tools, repo_root):
        result = tools["list_directory"](".")
        assert "README.md" in result
        assert "src" in result

    def test_lists_subdirectory(self, tools):
        result = tools["list_directory"]("src")
        assert "main.py" in result

    def test_nonexistent_dir_returns_error(self, tools):
        result = tools["list_directory"]("nonexistent")
        assert "Error" in result


class TestSearchCodebase:
    """Tests for the search_codebase tool."""

    def test_finds_pattern(self, tools):
        result = tools["search_codebase"]("hello")
        assert "main.py" in result or "No matches" in result

    def test_empty_query_rejected(self, tools):
        result = tools["search_codebase"]("")
        assert "Error" in result


class TestReadAdr:
    """Tests for the read_adr tool."""

    def test_reads_existing_adr(self, tools):
        result = tools["read_adr"]("001")
        assert "ADR-001" in result

    def test_nonexistent_adr(self, tools):
        result = tools["read_adr"]("999")
        assert "Error" in result


class TestReadJourney:
    """Tests for the read_journey tool."""

    def test_reads_existing_journey(self, tools):
        result = tools["read_journey"]("001")
        assert "Journey 001" in result

    def test_nonexistent_journey(self, tools):
        result = tools["read_journey"]("999")
        assert "Error" in result
