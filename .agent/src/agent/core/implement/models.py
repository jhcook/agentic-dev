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

"""Pydantic models for implementation runbook validation."""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from pathlib import Path
from agent.core.config import resolve_repo_path


class ParsingError(ValueError):
    """Raised when the runbook content cannot be parsed into the expected structure."""

    pass


class SearchReplaceBlock(BaseModel):
    """A single SEARCH/REPLACE pair within a MODIFY operation."""

    search: str = Field(..., min_length=1, description="The exact text to find.")
    replace: str = Field(..., description="The replacement text.")

    @field_validator("search")
    @classmethod
    def search_must_not_be_empty(cls, v: str) -> str:
        """Ensure search block is not just whitespace and strip it."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("SEARCH block cannot be empty or only whitespace.")
        return stripped

    @field_validator("replace")
    @classmethod
    def replace_must_not_be_empty(cls, v: str) -> str:
        """Reject whitespace-only replace blocks; permit empty strings (deletions)."""
        if v == "":
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("REPLACE block cannot contain only whitespace.")
        return stripped

class ModifyBlock(BaseModel):
    """An operation to modify an existing file."""

    path: str = Field(..., description="Repository-relative path to existing file.")
    blocks: List[SearchReplaceBlock] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_modify_contents(self) -> "ModifyBlock":
        """Verify the block contains operations and the path is valid."""
        if not self.blocks:
            raise ValueError(
                "MODIFY block must contain at least one valid SEARCH/REPLACE block."
            )
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
        # AC-3: Use canonical resolver for traversal + absolute path safety
        try:
            resolved = resolve_repo_path(self.path)
        except ValueError as e:
            raise ValueError(f"Path must be repository-relative and safe: {self.path}") from e
        # AC-3: Re-enable parent directory check via config.repo_root (INFRA-138)
        if not resolved.parent.exists():
            raise ValueError(
                f"Parent directory does not exist: {resolved.parent} "
                f"(from path '{self.path}')"
            )
        return self

class NewBlock(BaseModel):
    """An operation to create a new file."""
    
    path: str = Field(..., description="Repository-relative path for the new file.")
    content: str = Field(..., min_length=1, description="Complete file content.")

    @field_validator("path")
    @classmethod
    def validate_new_path(cls, v: str) -> str:
        """Ensure path is repository-relative and safe."""
        if not v:
            raise ValueError("Path is required for NEW block.")
        if ".." in v or v.startswith("/"):
            raise ValueError(f"Path must be repository-relative and safe: {v}")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate new file content is non-empty (stripping whitespace) and doesn't contain SEARCH blocks."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("NEW file content cannot be empty.")
        # AC-5(b): NEW blocks must not contain <<<SEARCH blocks
        if "<<<SEARCH" in v:
            raise ValueError(
                "[NEW] file content must not contain <<<SEARCH blocks. "
                "Use [MODIFY] with search/replace instead."
            )
        return stripped

class DeleteBlock(BaseModel):
    """An operation to remove a file."""
    
    path: str = Field(..., description="Repository-relative path to delete.")
    rationale: str = Field(..., min_length=5, description="Rationale for deletion.")

    @field_validator("path")
    @classmethod
    def validate_delete_path(cls, v: str) -> str:
        """Ensure path is repository-relative and safe."""
        if not v:
            raise ValueError("Path is required for DELETE block.")
        if ".." in v or v.startswith("/"):
            raise ValueError(f"Path must be repository-relative and safe: {v}")
        return v

class RunbookStep(BaseModel):
    """A logical step in the implementation containing one or more operations."""
    
    title: str = Field(..., min_length=5, description="Step title.")
    operations: List[Union[ModifyBlock, NewBlock, DeleteBlock]] = Field(default_factory=list)

class RunbookSchema(BaseModel):
    """The complete structure of a runbook implementation section."""
    
    steps: List[RunbookStep] = Field(..., min_length=1)
