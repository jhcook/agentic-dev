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

"""Unit tests for INFRA-150 strict block-level Pydantic validation rules."""

import pytest
from pydantic import ValidationError

from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    SearchReplaceBlock,
)


# ---------------------------------------------------------------------------
# AC-1: SearchReplaceBlock – whitespace stripping & empty rejection
# ---------------------------------------------------------------------------

class TestSearchReplaceBlock:
    """Tests for SearchReplaceBlock validators (AC-1)."""

    def test_valid_search_replace(self):
        """A well-formed block validates and strips leading/trailing whitespace."""
        block = SearchReplaceBlock(search="  old code  ", replace="  new code  ")
        assert block.search == "old code"
        assert block.replace == "new code"

    def test_empty_search_raises(self):
        """An empty search string must be rejected."""
        with pytest.raises(ValidationError):
            SearchReplaceBlock(search="", replace="valid")

    def test_whitespace_only_search_raises(self):
        """A whitespace-only search string must be rejected."""
        with pytest.raises(ValidationError, match="SEARCH block cannot be empty"):
            SearchReplaceBlock(search="   \n\t  ", replace="valid")

    def test_empty_replace_is_valid(self):
        """An empty replace string is valid (represents deletion of search text)."""
        block = SearchReplaceBlock(search="old code", replace="")
        assert block.replace == ""

    def test_whitespace_only_replace_raises(self):
        """A whitespace-only replace string must be rejected."""
        with pytest.raises(ValidationError, match="REPLACE block cannot contain only whitespace"):
            SearchReplaceBlock(search="valid", replace="   \n\t  ")


# ---------------------------------------------------------------------------
# AC-2: ModifyBlock – must contain at least one SearchReplaceBlock
# ---------------------------------------------------------------------------

class TestModifyBlock:
    """Tests for ModifyBlock model_validator (AC-2)."""

    def test_valid_modify_block(self):
        """A ModifyBlock with one S/R pair validates successfully."""
        # Use a path whose parent directory actually exists in the repo
        block = ModifyBlock(
            path=".agent/src/agent/core/implement/models.py",
            blocks=[SearchReplaceBlock(search="old", replace="new")],
        )
        assert block.path == ".agent/src/agent/core/implement/models.py"
        assert len(block.blocks) == 1

    def test_empty_blocks_list_raises(self):
        """An empty blocks list must be rejected by Pydantic min_length."""
        with pytest.raises(ValidationError):
            ModifyBlock(path="src/main.py", blocks=[])

    def test_missing_path_raises(self):
        """A ModifyBlock without a path must be rejected."""
        with pytest.raises(ValidationError):
            ModifyBlock(
                path="",
                blocks=[SearchReplaceBlock(search="old", replace="new")],
            )

    def test_traversal_path_raises(self):
        """A path with '..' traversal must be rejected."""
        with pytest.raises(ValidationError, match="repository-relative and safe"):
            ModifyBlock(
                path="../etc/passwd",
                blocks=[SearchReplaceBlock(search="old", replace="new")],
            )

    def test_absolute_path_raises(self):
        """An absolute path must be rejected."""
        with pytest.raises(ValidationError, match="repository-relative and safe"):
            ModifyBlock(
                path="/etc/passwd",
                blocks=[SearchReplaceBlock(search="old", replace="new")],
            )


# ---------------------------------------------------------------------------
# AC-3: DeleteBlock – rationale minimum length
# ---------------------------------------------------------------------------

class TestDeleteBlock:
    """Tests for DeleteBlock.rationale min_length=5 (AC-3)."""

    def test_valid_delete_block(self):
        """A DeleteBlock with a meaningful rationale validates successfully."""
        block = DeleteBlock(path="old_module.py", rationale="No longer needed after refactor")
        assert block.rationale == "No longer needed after refactor"

    def test_short_rationale_raises(self):
        """A rationale shorter than 5 characters must be rejected."""
        with pytest.raises(ValidationError, match="String should have at least 5 characters"):
            DeleteBlock(path="old.py", rationale="rm")

    def test_empty_rationale_raises(self):
        """An empty rationale must be rejected."""
        with pytest.raises(ValidationError):
            DeleteBlock(path="old.py", rationale="")

    def test_exact_minimum_rationale(self):
        """A rationale of exactly 5 characters should pass."""
        block = DeleteBlock(path="old.py", rationale="stale")
        assert block.rationale == "stale"

    def test_traversal_path_raises(self):
        """A delete path with '..' traversal must be rejected."""
        with pytest.raises(ValidationError, match="repository-relative and safe"):
            DeleteBlock(path="../secret", rationale="Valid rationale here")

    def test_absolute_path_raises(self):
        """An absolute delete path must be rejected."""
        with pytest.raises(ValidationError, match="repository-relative and safe"):
            DeleteBlock(path="/etc/passwd", rationale="Valid rationale here")


# ---------------------------------------------------------------------------
# AC-4 (Negative): NewBlock – content validation
# ---------------------------------------------------------------------------

class TestNewBlock:
    """Tests for NewBlock content validation."""

    def test_valid_new_block(self):
        """A NewBlock with content validates and strips whitespace."""
        block = NewBlock(path="new_file.py", content="  print('hello')  ")
        assert block.content == "print('hello')"

    def test_empty_content_raises(self):
        """Empty content must be rejected."""
        with pytest.raises(ValidationError):
            NewBlock(path="new_file.py", content="")

    def test_whitespace_only_content_raises(self):
        """Whitespace-only content must be rejected."""
        with pytest.raises(ValidationError, match="NEW file content cannot be empty"):
            NewBlock(path="new_file.py", content="   \n\t  ")

    def test_content_with_search_block_raises(self):
        """Content containing <<<SEARCH must be rejected."""
        with pytest.raises(ValidationError, match="must not contain <<<SEARCH"):
            NewBlock(path="new_file.py", content="<<<SEARCH\nold\n===\nnew\n>>>")

    def test_traversal_path_raises(self):
        """A new file path with '..' must be rejected."""
        with pytest.raises(ValidationError, match="repository-relative and safe"):
            NewBlock(path="../escape.py", content="valid content")
