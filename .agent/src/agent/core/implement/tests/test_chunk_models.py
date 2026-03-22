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
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock


def test_runbook_block_creation():
    """Test creating a RunbookBlock with required fields."""
    block = RunbookBlock(id="block-1", content="Hello world")
    assert block.id == "block-1"
    assert block.content == "Hello world"
    assert block.metadata == {}
    assert block.prefix_whitespace == ""
    assert block.suffix_whitespace == ""
    assert block.block_type == "markdown"


def test_runbook_block_with_metadata():
    """Test creating a RunbookBlock with metadata."""
    block = RunbookBlock(
        id="block-2",
        content="Content",
        metadata={"version": "2.0", "tags": "infra,test"},
    )
    assert block.metadata["version"] == "2.0"
    assert "infra" in block.metadata["tags"]


def test_skeleton_get_block_found():
    """Test retrieving a block by ID from a skeleton."""
    blocks = [
        RunbookBlock(id="a", content="first"),
        RunbookBlock(id="b", content="second"),
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    result = skeleton.get_block("b")
    assert result is not None
    assert result.content == "second"


def test_skeleton_get_block_not_found():
    """Test retrieving a nonexistent block returns None."""
    skeleton = RunbookSkeleton(blocks=[RunbookBlock(id="a", content="x")])
    assert skeleton.get_block("missing") is None


def test_skeleton_defaults():
    """Test RunbookSkeleton default field values."""
    skeleton = RunbookSkeleton(blocks=[])
    assert skeleton.source_path is None
    assert skeleton.version == "1.0.0"
    assert skeleton.blocks == []