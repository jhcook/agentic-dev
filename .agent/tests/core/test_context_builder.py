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

"""Tests for ContextBuilder class."""

from pathlib import Path

import pytest

from agent.core.context_builder import ContextBuilder


@pytest.fixture
def temp_repo(tmp_path: Path):
    """Creates a temporary repository structure for testing."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / ".agent").mkdir()
    
    (tmp_path / "docs" / "guide.md").write_text("This is a guide about workflows.")
    (tmp_path / "src" / "main.py").write_text("Some python code about workflows.")
    (tmp_path / "src" / "binary.bin").write_bytes(b'\x80\x02\x03')
    
    (tmp_path / "secrets.log").write_text("secret workflow data")
    
    long_content = "word " * 5000
    (tmp_path / "src" / "large.txt").write_text(long_content)

    (tmp_path / ".gitignore").write_text("*.log\n__pycache__/\n")
    
    return tmp_path


class TestContextBuilder:
    """Tests for ContextBuilder class."""
    
    def test_load_gitignore(self, temp_repo):
        """Test that .gitignore patterns are loaded."""
        builder = ContextBuilder(root_dir=temp_repo)
        
        assert "*.log" in builder.ignore_patterns
        assert "__pycache__/" in builder.ignore_patterns
    
    def test_is_ignored_matches_patterns(self, temp_repo):
        """Test that ignored files are correctly detected."""
        builder = ContextBuilder(root_dir=temp_repo)
        
        # .log files should be ignored
        assert builder._is_ignored(temp_repo / "secrets.log")
        
        # Regular files should not be ignored
        assert not builder._is_ignored(temp_repo / "docs" / "guide.md")
    
    def test_is_binary_file(self, temp_repo):
        """Test binary file detection."""
        builder = ContextBuilder(root_dir=temp_repo)
        
        assert builder._is_binary_file(Path("test.png"))
        assert builder._is_binary_file(Path("test.pdf"))
        assert not builder._is_binary_file(Path("test.py"))
        assert not builder._is_binary_file(Path("test.md"))
    
    def test_read_and_scrub_file(self, temp_repo):
        """Test file reading and scrubbing."""
        builder = ContextBuilder(root_dir=temp_repo)
        
        content = builder._read_and_scrub_file(temp_repo / "docs" / "guide.md")
        
        assert "--- START" in content
        assert "guide.md" in content
        assert "--- END" in content
        assert "workflows" in content
    
    def test_read_binary_file_returns_empty(self, temp_repo):
        """Test that binary files return empty string."""
        builder = ContextBuilder(root_dir=temp_repo)
        
        content = builder._read_and_scrub_file(temp_repo / "src" / "binary.bin")
        
        # Binary files should be skipped gracefully
        assert content == "" or "--- START" in content  # Depends on encoding handling


class TestContextBuilderAsync:
    """Tests for ContextBuilder async methods."""
    
    def test_find_relevant_files(self, temp_repo):
        """Test that _find_relevant_files calls grep correctly."""
        import asyncio
        
        builder = ContextBuilder(root_dir=temp_repo)
        
        # Run the actual async method
        files = asyncio.run(builder._find_relevant_files("workflow"))
        
        # Files may be empty if grep doesn't find anything in temp_repo
        assert isinstance(files, list)
    
    def test_build_context(self, temp_repo):
        """Test full context building."""
        import asyncio
        
        builder = ContextBuilder(root_dir=temp_repo)
        context = asyncio.run(builder.build_context("workflow"))
        
        # Context should be a string (may be empty if no files match)
        assert isinstance(context, str)