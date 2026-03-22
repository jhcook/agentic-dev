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

"""chunk_models module."""

# Copyright 2026 Justin Cook

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RunbookBlock(BaseModel):
    """Represents a discrete, addressable segment of a runbook.

    Attributes:
        id: A unique identifier for the block, usually derived from comments.
        content: The raw text content of the block excluding boundaries.
        metadata: Key-value pairs extracted from block tags (e.g., tags, version).
        prefix_whitespace: Exact whitespace/newlines preceding the block content.
        suffix_whitespace: Exact whitespace/newlines following the block content.
        block_type: The source format (e.g., 'markdown', 'yaml').
    """
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    prefix_whitespace: str = ""
    suffix_whitespace: str = ""
    block_type: str = "markdown"

class RunbookSkeleton(BaseModel):
    """A complete collection of blocks representing a full runbook template."""
    blocks: List[RunbookBlock]
    source_path: Optional[str] = None
    version: str = "1.0.0"

    def get_block(self, block_id: str) -> Optional[RunbookBlock]:
        """Retrieve a specific block by its ID."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None
