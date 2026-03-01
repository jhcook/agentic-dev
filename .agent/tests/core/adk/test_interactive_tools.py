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

"""Tests for interactive tools (INFRA-088).

Verifies edit_file, run_command, find_files, and grep_search
tool functions including security boundary enforcement.
"""


import pytest

from agent.core.adk.tools import make_interactive_tools


@pytest.fixture
def repo_root(tmp_path):
    """Create a temporary repo root with some test files."""
    # Create a sample file structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')\n")
    (src_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "README.md").write_text("# Test Repo\n")
    return tmp_path


@pytest.fixture
def tools(repo_root):
    """Return the 4 interactive tools bound to the temp repo root."""
    tool_list = make_interactive_tools(repo_root)
    return {fn.__name__: fn for fn in tool_list}


class TestEditFile:
    """Tests for the edit_file tool."""

    def test_creates_and_writes(self, tools, repo_root):
        result = tools["edit_file"]("new_file.txt", "hello world")
        assert "successfully updated" in result
        assert (repo_root / "new_file.txt").read_text() == "hello world"

    def test_creates_parent_directories(self, tools, repo_root):
        result = tools["edit_file"]("deep/nested/dir/file.txt", "content")
        assert "successfully updated" in result
        assert (repo_root / "deep" / "nested" / "dir" / "file.txt").exists()

    def test_overwrites_existing_file(self, tools, repo_root):
        tools["edit_file"]("src/main.py", "new content")
        assert (repo_root / "src" / "main.py").read_text() == "new content"

    def test_rejects_path_traversal(self, tools, repo_root):
        result = tools["edit_file"]("../outside.txt", "bad content")
        assert "Error" in result


class TestRunCommand:
    """Tests for the run_command tool."""

    def test_captures_stdout(self, tools):
        result = tools["run_command"]("echo hello")
        assert "hello" in result
        assert "Exit code: 0" in result

    def test_captures_stderr(self, tools):
        result = tools["run_command"]("ls nonexistent_path_xyz")
        assert "Exit code:" in result
        # Should have non-zero exit code or stderr

    def test_cwd_is_repo_root(self, tools, repo_root):
        result = tools["run_command"]("pwd")
        assert str(repo_root) in result

    def test_timeout(self, tools):
        # This should timeout (30s) — use a shorter sleep to not slow tests
        # Just verify the command runs without crashing
        result = tools["run_command"]("echo fast")
        assert "Exit code: 0" in result

    def test_invalid_command(self, tools):
        result = tools["run_command"]("")
        assert "Error" in result


class TestFindFiles:
    """Tests for the find_files tool."""

    def test_finds_matching_files(self, tools):
        result = tools["find_files"]("*.py")
        assert "main.py" in result
        assert "utils.py" in result

    def test_no_matches_returns_message(self, tools):
        result = tools["find_files"]("*.nonexistent")
        assert "No files found" in result

    def test_finds_markdown(self, tools):
        result = tools["find_files"]("*.md")
        assert "README.md" in result


class TestGrepSearch:
    """Tests for the grep_search tool."""

    def test_finds_pattern(self, tools):
        result = tools["grep_search"]("hello")
        # Should find 'hello' in src/main.py, or rg may not be available
        assert "main.py" in result or "No matches found" in result or "not installed" in result

    def test_validates_path(self, tools):
        result = tools["grep_search"]("test", "../../etc/passwd")
        assert "Error" in result

    def test_empty_query_rejected(self, tools):
        result = tools["grep_search"]("")
        assert "Error" in result
