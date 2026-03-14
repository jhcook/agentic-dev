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

"""Unit tests for Pydantic runbook validation models."""

import pytest
from pydantic import ValidationError

from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    RunbookSchema,
    RunbookStep,
    SearchReplaceBlock,
)


# ── SearchReplaceBlock ───────────────────────────────────────


class TestSearchReplaceBlock:
    def test_valid_block(self):
        block = SearchReplaceBlock(search="old_code()", replace="new_code()")
        assert block.search == "old_code()"
        assert block.replace == "new_code()"

    def test_empty_search_rejected(self):
        with pytest.raises(ValidationError, match="SEARCH block cannot be empty"):
            SearchReplaceBlock(search="   ", replace="replacement")

    def test_empty_replace_allowed(self):
        """Deletions use empty replace strings — must be allowed."""
        block = SearchReplaceBlock(search="remove_me()", replace="")
        assert block.replace == ""


# ── ModifyBlock ──────────────────────────────────────────────


class TestModifyBlock:
    def test_valid_modify(self):
        block = ModifyBlock(
            path="src/main.py",
            blocks=[SearchReplaceBlock(search="old", replace="new")],
        )
        assert block.path == "src/main.py"

    def test_empty_blocks_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 item"):
            ModifyBlock(path="src/main.py", blocks=[])

    def test_absolute_path_rejected(self):
        with pytest.raises(ValidationError, match="repository-relative"):
            ModifyBlock(
                path="/etc/passwd",
                blocks=[SearchReplaceBlock(search="a", replace="b")],
            )

    def test_traversal_path_rejected(self):
        with pytest.raises(ValidationError, match="repository-relative"):
            ModifyBlock(
                path="../../../etc/passwd",
                blocks=[SearchReplaceBlock(search="a", replace="b")],
            )

    def test_hallucinated_directory_rejected(self, tmp_path, monkeypatch):
        """AC-4(c): parent directory must exist."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValidationError, match="does not exist"):
            ModifyBlock(
                path="nonexistent/dir/file.py",
                blocks=[SearchReplaceBlock(search="a", replace="b")],
            )


# ── NewBlock ─────────────────────────────────────────────────


class TestNewBlock:
    def test_valid_new(self):
        block = NewBlock(path="src/new.py", content="print('hello')")
        assert block.path == "src/new.py"

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            NewBlock(path="src/new.py", content="   ")

    def test_search_block_in_content_rejected(self):
        """AC-5(b): NEW blocks must not contain <<<SEARCH."""
        with pytest.raises(ValidationError, match="must not contain.*SEARCH"):
            NewBlock(
                path="src/new.py",
                content="<<<SEARCH\nold_code\n===\nnew_code\n>>>",
            )


# ── DeleteBlock ──────────────────────────────────────────────


class TestDeleteBlock:
    def test_valid_delete(self):
        block = DeleteBlock(path="old_file.py", rationale="No longer needed after refactor")
        assert block.rationale == "No longer needed after refactor"

    def test_short_rationale_rejected(self):
        with pytest.raises(ValidationError, match="at least 5"):
            DeleteBlock(path="old.py", rationale="rm")


# ── RunbookStep ──────────────────────────────────────────────


class TestRunbookStep:
    def test_valid_step(self):
        step = RunbookStep(
            title="Create the new module",
            operations=[NewBlock(path="mod.py", content="x = 1")],
        )
        assert step.title == "Create the new module"
        assert len(step.operations) == 1

    def test_short_title_rejected(self):
        with pytest.raises(ValidationError, match="at least 5"):
            RunbookStep(
                title="Fix",
                operations=[NewBlock(path="mod.py", content="x = 1")],
            )

    def test_no_operations_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 item"):
            RunbookStep(title="Valid title here", operations=[])


# ── RunbookSchema ────────────────────────────────────────────


class TestRunbookSchema:
    def test_valid_schema(self):
        schema = RunbookSchema(
            steps=[
                RunbookStep(
                    title="Create the new module",
                    operations=[NewBlock(path="mod.py", content="x = 1")],
                )
            ]
        )
        assert len(schema.steps) == 1

    def test_empty_steps_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 item"):
            RunbookSchema(steps=[])
