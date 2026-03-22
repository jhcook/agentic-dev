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

"""assembly_engine module."""

# Copyright 2026 Justin Cook

from agent.core.implement.chunk_models import RunbookSkeleton

from typing import Dict, Optional

class InvalidTemplateError(Exception):
    """Raised when a skeleton template is malformed or assembly fails."""
    pass

class AssemblyEngine:
    """Engine responsible for reconstructing documents from block maps."""

    def assemble(
        self, 
        skeleton: RunbookSkeleton, 
        injections: Optional[Dict[str, str]] = None
    ) -> str:
        """Reconstruct the document from a RunbookSkeleton.

        Ensures exact preservation of whitespace and styling by concatenating
        blocks in their original order. Supports partial content injection.

        Args:
            skeleton: The parsed RunbookSkeleton containing blocks.
            injections: Optional mapping of block IDs to replacement content.

        Returns:
            The fully assembled document string.

        Raises:
            InvalidTemplateError: If the skeleton has no blocks or duplicate IDs.
        """
        if not skeleton.blocks:
            raise InvalidTemplateError("Cannot assemble an empty skeleton.")

        injections = injections or {}
        seen_ids = set()
        parts = []

        for block in skeleton.blocks:
            if block.id in seen_ids:
                raise InvalidTemplateError(f"Duplicate block ID detected: {block.id}")
            seen_ids.add(block.id)

            # Use injected content if ID matches, else original block content
            content = injections.get(block.id, block.content)

            parts.append(block.prefix_whitespace)
            parts.append(content)
            parts.append(block.suffix_whitespace)

        return "".join(parts)
