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

"""test_assembly_engine module."""

# Copyright 2026 Justin Cook

import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError

def test_assemble_round_trip():
    """Verify that a skeleton can be reconstructed exactly without injections."""
    blocks = [
        RunbookBlock(
            id="header", 
            content="# Title", 
            prefix_whitespace="", 
            suffix_whitespace="\n\n"
        ),
        RunbookBlock(
            id="body", 
            content="This is the body.", 
            prefix_whitespace="", 
            suffix_whitespace="\n"
        )
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    result = engine.assemble(skeleton)
    assert result == "# Title\n\nThis is the body.\n"

def test_assemble_with_injection():
    """Verify that injected content replaces the original block content."""
    blocks = [
        RunbookBlock(id="b1", content="Original", suffix_whitespace=" "),
        RunbookBlock(id="b2", content="Text", suffix_whitespace="")
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    injections = {"b1": "Modified"}
    result = engine.assemble(skeleton, injections=injections)
    assert result == "Modified Text"

def test_assemble_preserves_whitespace_around_injection():
    """Verify that whitespace is preserved even when content is injected."""
    blocks = [
        RunbookBlock(
            id="b1", 
            content="[BLOCK]", 
            prefix_whitespace="  ", 
            suffix_whitespace="  "
        )
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    result = engine.assemble(skeleton, injections={"b1": "NEW"})
    assert result == "  NEW  "

def test_assemble_empty_skeleton_raises():
    """Verify that an empty skeleton triggers InvalidTemplateError."""
    skeleton = RunbookSkeleton(blocks=[])
    engine = AssemblyEngine()
    with pytest.raises(InvalidTemplateError, match="empty skeleton"):
        engine.assemble(skeleton)

def test_assemble_duplicate_ids_raises():
    """Verify that duplicate block IDs trigger InvalidTemplateError."""
    blocks = [
        RunbookBlock(id="dup", content="one"),
        RunbookBlock(id="dup", content="two")
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    with pytest.raises(InvalidTemplateError, match="Duplicate block ID"):
        engine.assemble(skeleton)
