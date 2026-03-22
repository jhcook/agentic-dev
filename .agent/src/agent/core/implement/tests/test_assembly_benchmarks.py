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

"""test_assembly_benchmarks module."""

# Copyright 2026 Justin Cook

import time
import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock
from agent.core.implement.assembly_engine import AssemblyEngine
from agent.core.implement.parser import parse_skeleton

def test_performance_benchmarks():
    """Ensure that parsing and assembly of a 50-block runbook completes in < 250ms."""
    # Setup 50 addressable blocks to simulate a standard complex runbook
    parts = [f"<!-- @block b{i} -->\nBlock {i} Content\n<!-- @end -->" for i in range(50)]
    source = "\n\n".join(parts)
    
    engine = AssemblyEngine()
    
    start = time.perf_counter()
    
    # Execute full pipeline: Parse -> Model -> Assemble
    skeleton = parse_skeleton(source)
    reconstructed = engine.assemble(skeleton)
    
    duration_ms = (time.perf_counter() - start) * 1000
    
    # Requirement: Performance < 250ms
    assert duration_ms < 250, f"Performance benchmark failed: {duration_ms:.2f}ms exceeds 250ms limit"
    assert len(skeleton.blocks) == 50
    assert "Block 49 Content" in reconstructed

def test_round_trip_zero_deviation():
    """Verify 0% deviation between source and re-assembled output to ensure whitespace preservation."""
    source = (
        "# Runbook Skeleton\n\n"
        "<!-- @block b1 -->\n"
        "## Section A\n"
        "Content with specific whitespace and formatting.\n\n"
        "<!-- @end -->\n\n"
        "<!-- @block b2 -->\n"
        "## Section B\n"
        "More content.\n"
        "<!-- @end -->"
    )
    
    engine = AssemblyEngine()
    skeleton = parse_skeleton(source)
    reconstructed = engine.assemble(skeleton)
    
    # Requirement: 0% deviation integration test
    assert reconstructed == source, "Integration 'Round Trip' test failed: Output differs from source string"

def test_partial_injection_integrity():
    """Verify that injecting partial content does not corrupt the surrounding block structure."""
    source = "<!-- @block b1 -->Original<!-- @end -->"
    skeleton = parse_skeleton(source)
    engine = AssemblyEngine()
    
    output = engine.assemble(skeleton, injections={"b1": "Modified"})
    assert output == "<!-- @block b1 -->Modified<!-- @end -->"
