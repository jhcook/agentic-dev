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

class SearchReplaceBlock(BaseModel):
    """A single SEARCH/REPLACE pair within a MODIFY operation."""
    
    search: str = Field(..., min_length=1, description="The exact text to find.")
    replace: str = Field(..., description="The replacement text.")

    @field_validator("search")
    @classmethod
    def search_must_not_be_empty(cls, v: str) -> str:
        """Ensure search block is not just whitespace."""
        if not v.strip():
            raise ValueError("SEARCH block cannot be empty or only whitespace.")
        return v

class ModifyBlock(BaseModel):
    """An operation to modify an existing file."""
    
    path: str = Field(..., description="Repository-relative path to existing file.")
    blocks: List[SearchReplaceBlock] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_modify_path(self) -> "ModifyBlock":
        """Verify the path is valid for a modification."""
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
        # Basic relative path safety
        if ".." in self.path or self.path.startswith("/"):
            raise ValueError(f"Path must be repository-relative and safe: {self.path}")
        # AC-4(c): parent directory must exist
        parent = Path(self.path).parent
        if str(parent) != "." and not parent.exists():
            raise ValueError(
                f"[MODIFY] '{self.path}': parent directory '{parent}' does not exist. "
                f"Check for hallucinated paths."
            )
        return self

class NewBlock(BaseModel):
    """An operation to create a new file."""
    
    path: str = Field(..., description="Repository-relative path for the new file.")
    content: str = Field(..., min_length=1, description="Complete file content.")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate new file content is non-empty and doesn't contain SEARCH blocks."""
        if not v.strip():
            raise ValueError("NEW file content cannot be empty.")
        # AC-5(b): NEW blocks must not contain <<<SEARCH blocks
        if "<<<SEARCH" in v:
            raise ValueError(
                "[NEW] file content must not contain <<<SEARCH blocks. "
                "Use [MODIFY] with search/replace instead."
            )
        return v

class DeleteBlock(BaseModel):
    """An operation to remove a file."""
    
    path: str = Field(..., description="Repository-relative path to delete.")
    rationale: str = Field(..., min_length=5, description="Rationale for deletion.")

class RunbookStep(BaseModel):
    """A logical step in the implementation containing one or more operations."""
    
    title: str = Field(..., min_length=5, description="Step title.")
    operations: List[Union[ModifyBlock, NewBlock, DeleteBlock]] = Field(..., min_length=1)

class RunbookSchema(BaseModel):
    """The complete structure of a runbook implementation section."""
    
    steps: List[RunbookStep] = Field(..., min_length=1)
