# Copyright 2026 Justin Cook
"""Tests for idempotency guards in apply_search_replace_to_file and apply_change_to_file.

Covers:
- S/R block skip when REPLACE content already present (AC: idempotent re-run)
- Full-file skip when file has identical content (AC: no-op on re-apply)
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.implement.guards import (
    apply_search_replace_to_file,
    apply_change_to_file,
)

# Deferred-import targets patched at their source modules.
_RESOLVE_PATH = "agent.core.implement.orchestrator.resolve_path"
_RESOLVE_REPO = "agent.core.config.resolve_repo_path"
_BACKUP_FILE = "agent.core.implement.guards.backup_file"
_LICENSE = "agent.commands.license.apply_license_to_file"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_source_file(tmp_path: Path) -> Path:
    """Create a temporary Python source file for testing."""
    f = tmp_path / "example.py"
    f.write_text("def hello():\n    print('hello')\n")
    return f


@pytest.fixture
def repo_path_factory(tmp_path: Path):
    """Return a side_effect for resolve_repo_path that joins args to tmp_path."""
    def _resolve(rel: str) -> Path:
        return tmp_path / rel
    return _resolve


# ---------------------------------------------------------------------------
# apply_search_replace_to_file — idempotency
# ---------------------------------------------------------------------------

class TestSearchReplaceIdempotency:
    """Verify S/R blocks are skipped when REPLACE text already present."""

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_already_applied_block_is_skipped(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_source_file, tmp_path, repo_path_factory, caplog,
    ):
        """If REPLACE text already exists in the file, the block is skipped."""
        tmp_source_file.write_text("def hello():\n    print('world')\n")
        mock_resolve.return_value = tmp_source_file
        mock_repo.side_effect = repo_path_factory

        blocks = [{"search": "print('hello')", "replace": "print('world')"}]

        with caplog.at_level(logging.INFO):
            success, content = apply_search_replace_to_file(
                str(tmp_source_file), blocks, yes=True,
            )

        assert success is True
        assert "already_applied" in caplog.text

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_fresh_block_is_applied(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_source_file, tmp_path, repo_path_factory,
    ):
        """A block whose SEARCH text is present gets applied normally."""
        tmp_source_file.write_text("def hello():\n    print('hello')\n")
        mock_resolve.return_value = tmp_source_file
        mock_repo.side_effect = repo_path_factory

        blocks = [{"search": "print('hello')", "replace": "print('world')"}]

        success, content = apply_search_replace_to_file(
            str(tmp_source_file), blocks, yes=True,
        )

        assert success is True
        assert "print('world')" in content

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_double_apply_is_no_op(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_source_file, tmp_path, repo_path_factory, caplog,
    ):
        """Applying the same S/R twice should succeed both times (idempotent)."""
        original = "def hello():\n    print('hello')\n"
        tmp_source_file.write_text(original)
        mock_resolve.return_value = tmp_source_file
        mock_repo.side_effect = repo_path_factory

        blocks = [{"search": "print('hello')", "replace": "print('world')"}]

        # First apply
        success1, content1 = apply_search_replace_to_file(
            str(tmp_source_file), blocks, yes=True,
        )
        assert success1 is True
        tmp_source_file.write_text(content1)

        # Second apply — should skip (REPLACE already present)
        with caplog.at_level(logging.INFO):
            success2, content2 = apply_search_replace_to_file(
                str(tmp_source_file), blocks, yes=True,
            )

        assert success2 is True
        assert content2 == content1


# ---------------------------------------------------------------------------
# apply_change_to_file — idempotency
# ---------------------------------------------------------------------------

class TestApplyChangeIdempotency:
    """Verify full-file write is skipped when content is identical."""

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_identical_content_skips_write(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_source_file, tmp_path, repo_path_factory, caplog,
    ):
        """If file already has identical content, apply returns True without writing."""
        content = "def hello():\n    print('world')\n"
        tmp_source_file.write_text(content)
        mock_resolve.return_value = tmp_source_file
        mock_repo.side_effect = repo_path_factory

        with caplog.at_level(logging.INFO):
            result = apply_change_to_file(
                str(tmp_source_file), content, yes=True,
            )

        assert result is True
        assert "already_applied" in caplog.text

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_different_content_writes(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_source_file, tmp_path, repo_path_factory,
    ):
        """If content differs, the file is updated."""
        tmp_source_file.write_text("old content\n")
        mock_resolve.return_value = tmp_source_file
        mock_repo.side_effect = repo_path_factory

        new_content = "new content\n"
        result = apply_change_to_file(
            str(tmp_source_file), new_content, yes=True,
        )

        assert result is True
        assert tmp_source_file.read_text() == new_content

    @patch(_LICENSE, return_value=False)
    @patch(_BACKUP_FILE, return_value=None)
    @patch(_RESOLVE_REPO)
    @patch(_RESOLVE_PATH)
    def test_new_file_is_created(
        self, mock_resolve, mock_repo, _bk, _lic, tmp_path, repo_path_factory,
    ):
        """If file doesn't exist, it's created successfully."""
        new_file = tmp_path / "brand_new.py"
        mock_resolve.return_value = new_file
        mock_repo.side_effect = repo_path_factory

        result = apply_change_to_file(
            str(new_file), "# new file\n", yes=True,
        )

        assert result is True
        assert new_file.exists()
