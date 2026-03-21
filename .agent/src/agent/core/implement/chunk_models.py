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

"""Models for modular (chunked) runbook generation."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class SkeletonSection:
    """Represents a specific section in the implementation runbook skeleton."""

    title: str
    description: str
    estimated_tokens: int


@dataclass
class RunbookSkeleton:
    """Represents the high-level structural skeleton of a runbook."""

    title: str
    sections: List[SkeletonSection]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunbookSkeleton":
        """
        Create a RunbookSkeleton from a dictionary with basic validation.

        Args:
            data: The dictionary to parse.

        Returns:
            A populated RunbookSkeleton instance.

        Raises:
            ValueError: If required fields are missing or malformed.
        """
        if "title" not in data or "sections" not in data:
            raise ValueError("Skeleton JSON must contain 'title' and 'sections'")
        if not isinstance(data["sections"], list):
            raise ValueError("'sections' must be a JSON array")

        sections = [
            SkeletonSection(
                title=str(s.get("title", "Untitled")),
                description=str(s.get("description", "")),
                estimated_tokens=int(s.get("estimated_tokens", 0)),
            )
            for s in data["sections"]
        ]
        return cls(title=str(data["title"]), sections=sections)


@dataclass
class RunbookBlock:
    """Represents a detailed implementation block generated from a skeleton section."""

    header: str
    content: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunbookBlock":
        """
        Create a RunbookBlock from a dictionary with basic validation.

        Args:
            data: The dictionary to parse.

        Returns:
            A populated RunbookBlock instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if "header" not in data or "content" not in data:
            raise ValueError("Block JSON must contain 'header' and 'content'")
        return cls(header=str(data["header"]), content=str(data["content"]))