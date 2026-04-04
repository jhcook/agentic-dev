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

"""Models for structured runbook generation operations (INFRA-181)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RunbookOpJson(BaseModel):
    """Structured representation of a file operation in a generated runbook.

    Used to validate JSON output from the LLM before Python assembles
    the final markdown with <<<SEARCH/===/>>> delimiters.  The LLM never
    writes the delimiters — Python does.
    """

    op: Literal["modify", "new", "delete"] = Field(
        ..., description="The type of operation to perform."
    )
    file: str = Field(
        ..., description="The repository-relative path to the target file."
    )
    search: Optional[str] = Field(
        None, description="The exact text to find in the file. Required for 'modify'."
    )
    replace: Optional[str] = Field(
        None, description="The replacement text. Required for 'modify'."
    )
    content: Optional[str] = Field(
        None, description="Full file content (raw code, no fences). Required for 'new'."
    )
    rationale: Optional[str] = Field(
        None, description="The reason for deletion. Required for 'delete'."
    )

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> "RunbookOpJson":
        """Verify that required fields are present for each operation type."""
        if self.op == "modify":
            if self.search is None or self.replace is None:
                raise ValueError(
                    "Operations with op='modify' must provide both 'search' and 'replace' fields."
                )
        elif self.op == "new":
            if self.content is None:
                raise ValueError(
                    "Operations with op='new' must provide the 'content' field."
                )
        elif self.op == "delete":
            if self.rationale is None:
                raise ValueError(
                    "Operations with op='delete' must provide the 'rationale' field."
                )
        return self
