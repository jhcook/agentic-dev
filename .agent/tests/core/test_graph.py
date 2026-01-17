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

"""Tests for ProjectGraph class."""

import pytest
from pathlib import Path
from agent.core.graph import ProjectGraph, build_from_repo


@pytest.fixture
def fixture_dir(tmp_path):
    """Create a fixture directory with sample governance artifacts."""
    # Create directory structure
    plans_dir = tmp_path / ".agent" / "cache" / "plans" / "INFRA"
    stories_dir = tmp_path / ".agent" / "cache" / "stories" / "INFRA"
    runbooks_dir = tmp_path / ".agent" / "cache" / "runbooks" / "INFRA"
    
    plans_dir.mkdir(parents=True)
    stories_dir.mkdir(parents=True)
    runbooks_dir.mkdir(parents=True)
    
    # Create a Plan
    plan_content = """---
id: PLAN-001
title: Infrastructure Setup
---

# PLAN-001: Infrastructure Setup

## State
APPROVED
"""
    (plans_dir / "PLAN-001-infrastructure.md").write_text(plan_content)
    
    # Create a Story with parent_plan
    story_content = """---
id: STORY-001
title: Setup Database
parent_plan: PLAN-001
---

# STORY-001: Setup Database

## State
COMMITTED
"""
    (stories_dir / "STORY-001-database.md").write_text(story_content)
    
    # Create a Runbook with story_id
    runbook_content = """---
id: RUNBOOK-001
title: Database Implementation
story_id: STORY-001
---

# RUNBOOK-001: Database Implementation

## State
ACCEPTED

## Implementation Steps

### [NEW] src/db/connection.py
Create database connection module.
"""
    (runbooks_dir / "RUNBOOK-001-database.md").write_text(runbook_content)
    
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    """Create an empty directory."""
    return tmp_path


class TestProjectGraph:
    """Tests for ProjectGraph class."""

    def test_build_from_fixture(self, fixture_dir):
        """Test building graph from fixture directory with artifacts."""
        graph = ProjectGraph(str(fixture_dir))
        result = graph.build()
        
        assert "nodes" in result
        assert "edges" in result
        
        # Should have 3 nodes: PLAN, STORY, RUNBOOK
        node_ids = [n["id"] for n in result["nodes"]]
        assert "PLAN-001" in node_ids
        assert "STORY-001" in node_ids
        assert "RUNBOOK-001" in node_ids

    def test_build_creates_edges(self, fixture_dir):
        """Test that edges are correctly created between artifacts."""
        graph = ProjectGraph(str(fixture_dir))
        result = graph.build()
        
        edges = result["edges"]
        
        # New behavior: edges are created for runbooks linking to code files
        # The runbook fixture has [NEW] src/db/connection.py
        # So we expect an edge from RUNBOOK-001 to the code node
        has_code_edge = any(
            e["source"] == "RUNBOOK-001" and "connection" in e["target"]
            for e in edges
        )
        assert has_code_edge, f"Expected edge from RUNBOOK-001 to code file. Got edges: {edges}"

    def test_build_empty_directory(self, empty_dir):
        """Test building graph from an empty directory."""
        graph = ProjectGraph(str(empty_dir))
        result = graph.build()
        
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_node_contains_required_fields(self, fixture_dir):
        """Test that nodes contain all required fields."""
        graph = ProjectGraph(str(fixture_dir))
        result = graph.build()
        
        for node in result["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "title" in node
            assert "path" in node

    def test_node_types_correct(self, fixture_dir):
        """Test that node types are correctly identified."""
        graph = ProjectGraph(str(fixture_dir))
        result = graph.build()
        
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        
        assert nodes_by_id["PLAN-001"]["type"] == "plan"
        assert nodes_by_id["STORY-001"]["type"] == "story"
        assert nodes_by_id["RUNBOOK-001"]["type"] == "runbook"


class TestBuildFromRepo:
    """Tests for build_from_repo factory function."""

    def test_factory_returns_graph(self, fixture_dir):
        """Test that factory function returns a valid graph."""
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(fixture_dir)
            result = build_from_repo(".")
            
            assert "nodes" in result
            assert "edges" in result
            assert len(result["nodes"]) > 0
        finally:
            os.chdir(original_dir)
