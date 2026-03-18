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
Unit tests for agent.tools.filesystem.

Covers:
- read_file, edit_file, patch_file, create_file, delete_file, find_files
- New operations: move_file, copy_file, file_diff
- Sandbox enforcement (negative tests for each path-taking function)
- PII scrubbing on read_file output
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import filesystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Return a temporary directory that acts as the repo root."""
    return tmp_path


def _write(root: Path, rel: str, content: str = "hello\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_reads_content(self, repo):
        _write(repo, "a.txt", "line1\nline2\n")
        result = filesystem.read_file("a.txt", repo)
        assert "line1" in result
        assert "line2" in result

    def test_missing_file(self, repo):
        result = filesystem.read_file("missing.txt", repo)
        assert result.startswith("Error:")

    def test_truncates_at_2000_lines(self, repo):
        content = "x\n" * 2500
        _write(repo, "big.txt", content)
        result = filesystem.read_file("big.txt", repo)
        assert "truncated" in result

    def test_sandbox_escape_rejected(self, repo):
        result = filesystem.read_file("../../etc/passwd", repo)
        assert "Error" in result and "outside the repository root" in result

    def test_pii_scrubbed(self, repo):
        """scrub_sensitive_data is applied to output."""
        _write(repo, "pii.txt", "normal content")
        with patch("agent.tools.filesystem.scrub_sensitive_data", return_value="SCRUBBED") as mock_scrub:
            result = filesystem.read_file("pii.txt", repo)
        mock_scrub.assert_called_once()
        assert result == "SCRUBBED"


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

class TestEditFile:
    def test_writes_content(self, repo):
        result = filesystem.edit_file("sub/new.txt", "new content", repo)
        assert "successfully updated" in result
        assert (repo / "sub" / "new.txt").read_text() == "new content"

    def test_sandbox_escape_rejected(self, repo):
        result = filesystem.edit_file("../../evil.txt", "boom", repo)
        assert "Error" in result and "outside the repository root" in result


# ---------------------------------------------------------------------------
# patch_file
# ---------------------------------------------------------------------------

class TestPatchFile:
    def test_patches_unique_match(self, repo):
        _write(repo, "p.txt", "hello world")
        result = filesystem.patch_file("p.txt", "world", "python", repo)
        assert "successfully patched" in result
        assert (repo / "p.txt").read_text() == "hello python"

    def test_rejects_missing_file(self, repo):
        result = filesystem.patch_file("missing.txt", "x", "y", repo)
        assert result.startswith("Error:")

    def test_rejects_zero_matches(self, repo):
        _write(repo, "p.txt", "hello world")
        result = filesystem.patch_file("p.txt", "NOTFOUND", "y", repo)
        assert "not found" in result

    def test_rejects_multiple_matches(self, repo):
        _write(repo, "p.txt", "a a a")
        result = filesystem.patch_file("p.txt", "a", "b", repo)
        assert "matches" in result

    def test_sandbox_escape_rejected(self, repo):
        result = filesystem.patch_file("../../evil.txt", "a", "b", repo)
        assert "Error" in result and "outside the repository root" in result


# ---------------------------------------------------------------------------
# create_file
# ---------------------------------------------------------------------------

class TestCreateFile:
    def test_creates_new_file(self, repo):
        result = filesystem.create_file("brand_new.txt", "content", repo)
        assert "successfully created" in result
        assert (repo / "brand_new.txt").read_text() == "content"

    def test_rejects_existing_file(self, repo):
        _write(repo, "exists.txt")
        result = filesystem.create_file("exists.txt", "new", repo)
        assert result.startswith("Error:")

    def test_sandbox_escape_rejected(self, repo):
        result = filesystem.create_file("../../evil.txt", "x", repo)
        assert "Error" in result and "outside the repository root" in result


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

class TestDeleteFile:
    def test_deletes_existing_file(self, repo):
        p = _write(repo, "del.txt")
        result = filesystem.delete_file("del.txt", repo)
        assert "successfully deleted" in result
        assert not p.exists()

    def test_rejects_nonexistent(self, repo):
        result = filesystem.delete_file("ghost.txt", repo)
        assert result.startswith("Error:")

    def test_sandbox_escape_rejected(self, repo):
        result = filesystem.delete_file("../../etc/passwd", repo)
        assert "Error" in result and "outside the repository root" in result


# ---------------------------------------------------------------------------
# find_files
# ---------------------------------------------------------------------------

class TestFindFiles:
    def test_finds_matching_files(self, repo):
        _write(repo, "src/foo.py", "")
        _write(repo, "src/bar.py", "")
        _write(repo, "src/baz.txt", "")
        result = filesystem.find_files("*.py", repo)
        assert "foo.py" in result
        assert "bar.py" in result
        assert "baz.txt" not in result

    def test_no_matches(self, repo):
        result = filesystem.find_files("*.xyz_never", repo)
        assert "No files found" in result


# ---------------------------------------------------------------------------
# move_file  (NEW)
# ---------------------------------------------------------------------------

class TestMoveFile:
    def test_moves_within_sandbox(self, repo):
        _write(repo, "src.txt", "data")
        result = filesystem.move_file("src.txt", "dst.txt", repo)
        assert "Successfully moved" in result
        assert not (repo / "src.txt").exists()
        assert (repo / "dst.txt").read_text() == "data"

    def test_rejects_src_outside_sandbox(self, repo):
        result = filesystem.move_file("../../evil.txt", "dst.txt", repo)
        assert result.startswith("Error")

    def test_rejects_dst_outside_sandbox(self, repo):
        _write(repo, "src.txt", "data")
        result = filesystem.move_file("src.txt", "../../evil.txt", repo)
        assert result.startswith("Error")

    def test_rejects_missing_source(self, repo):
        result = filesystem.move_file("missing.txt", "dst.txt", repo)
        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# copy_file  (NEW)
# ---------------------------------------------------------------------------

class TestCopyFile:
    def test_copies_within_sandbox(self, repo):
        _write(repo, "orig.txt", "original")
        result = filesystem.copy_file("orig.txt", "copy.txt", repo)
        assert "Successfully copied" in result
        assert (repo / "orig.txt").exists()  # original still there
        assert (repo / "copy.txt").read_text() == "original"

    def test_rejects_src_outside_sandbox(self, repo):
        result = filesystem.copy_file("../../evil.txt", "dst.txt", repo)
        assert result.startswith("Error")

    def test_rejects_dst_outside_sandbox(self, repo):
        _write(repo, "src.txt", "data")
        result = filesystem.copy_file("src.txt", "../../evil.txt", repo)
        assert result.startswith("Error")

    def test_rejects_missing_source(self, repo):
        result = filesystem.copy_file("ghost.txt", "dst.txt", repo)
        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# file_diff  (NEW)
# ---------------------------------------------------------------------------

class TestFileDiff:
    def test_unified_diff_output(self, repo):
        _write(repo, "a.txt", "line1\nline2\n")
        _write(repo, "b.txt", "line1\nline3\n")
        result = filesystem.file_diff("a.txt", "b.txt", repo)
        assert "line2" in result
        assert "line3" in result

    def test_no_difference(self, repo):
        _write(repo, "a.txt", "same\n")
        _write(repo, "b.txt", "same\n")
        result = filesystem.file_diff("a.txt", "b.txt", repo)
        assert "No differences found" in result

    def test_rejects_path_a_outside_sandbox(self, repo):
        _write(repo, "b.txt", "x")
        result = filesystem.file_diff("../../etc/passwd", "b.txt", repo)
        assert result.startswith("Error")

    def test_rejects_path_b_outside_sandbox(self, repo):
        _write(repo, "a.txt", "x")
        result = filesystem.file_diff("a.txt", "../../etc/passwd", repo)
        assert result.startswith("Error")
