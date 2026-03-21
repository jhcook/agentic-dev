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

"""Tests for runbook chunking data models."""

import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock, SkeletonSection


def test_skeleton_from_dict_valid():
    """Test parsing a valid skeleton dictionary."""
    data = {
        "title": "Test Runbook",
        "sections": [
            {"title": "Section 1", "description": "Desc 1", "estimated_tokens": 100},
            {"title": "Section 2", "description": "Desc 2", "estimated_tokens": 200}
        ]
    }
    skeleton = RunbookSkeleton.from_dict(data)
    assert skeleton.title == "Test Runbook"
    assert len(skeleton.sections) == 2
    assert skeleton.sections[0].title == "Section 1"
    assert skeleton.sections[1].estimated_tokens == 200


def test_skeleton_from_dict_missing_fields():
    """Test parsing a skeleton with missing fields raises ValueError."""
    data = {"title": "Incomplete"}
    with pytest.raises(ValueError, match="Skeleton JSON must contain 'title' and 'sections'"):
        RunbookSkeleton.from_dict(data)


def test_skeleton_from_dict_invalid_sections():
    """Test parsing a skeleton with invalid sections raises ValueError."""
    data = {"title": "Bad Sections", "sections": "not a list"}
    with pytest.raises(ValueError, match="'sections' must be a JSON array"):
        RunbookSkeleton.from_dict(data)


def test_block_from_dict_valid():
    """Test parsing a valid block dictionary."""
    data = {
        "header": "Implementation Steps",
        "content": "### Step 1\nModify file.py"
    }
    block = RunbookBlock.from_dict(data)
    assert block.header == "Implementation Steps"
    assert "Modify file.py" in block.content


def test_block_from_dict_missing_fields():
    """Test parsing a block with missing fields raises ValueError."""
    data = {"header": "Missing Content"}
    with pytest.raises(ValueError, match="Block JSON must contain 'header' and 'content'"):
        RunbookBlock.from_dict(data)