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

"""Graph builder for project artifacts visualization."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)


class ProjectGraph:
    """Builds a graph representation of project artifacts."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []
        
        # Define artifact directories based on project structure
        self.plans_dir = self.root_path / ".agent" / "cache" / "plans"
        self.stories_dir = self.root_path / ".agent" / "cache" / "stories"
        self.runbooks_dir = self.root_path / ".agent" / "cache" / "runbooks"

    def _add_node(self, node_id: str, node_type: str, title: str, path: str) -> None:
        """Adds a node to the graph if it doesn't exist."""
        if node_id not in self.nodes:
            relative_path = os.path.relpath(path, self.root_path)
            self.nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "title": title,
                "path": relative_path,
            }
            logger.debug(f"Added node: {node_id} (type: {node_type})")

    def _add_edge(self, source: str, target: str) -> None:
        """Adds a directed edge to the graph."""
        edge = {"source": source, "target": target}
        if edge not in self.edges:
            self.edges.append(edge)
            logger.debug(f"Added edge: {source} -> {target}")

    def _extract_id_from_filename(self, file_path: Path) -> Optional[str]:
        """Extract artifact ID from filename like 'INFRA-016-runbook.md' -> 'INFRA-016'."""
        name = file_path.stem  # Remove .md
        # Match pattern like SCOPE-NNN (e.g., INFRA-016, MOBILE-001)
        match = re.match(r'^([A-Z]+-\d+)', name)
        if match:
            return match.group(1)
        return None

    def _extract_title_from_content(self, file_path: Path) -> str:
        """Extract title from first markdown header."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('# '):
                        # Remove the # and extract title after any ID prefix
                        header = line[2:].strip()
                        # Handle formats like "# INFRA-016: Title Here"
                        if ':' in header:
                            return header.split(':', 1)[1].strip()
                        return header
        except Exception as e:
            logger.warning(f"Could not read title from {file_path}: {e}")
        return "Untitled"

    def _determine_node_type(self, file_path: Path) -> str:
        """Determine artifact type based on directory or filename."""
        path_str = str(file_path)
        
        # Check by parent directory
        if '/plans/' in path_str or '\\plans\\' in path_str:
            return 'plan'
        elif '/stories/' in path_str or '\\stories\\' in path_str:
            return 'story'
        elif '/runbooks/' in path_str or '\\runbooks\\' in path_str:
            return 'runbook'
        
        # Fallback: check filename suffix
        name = file_path.stem.lower()
        if name.endswith('-runbook'):
            return 'runbook'
        elif 'plan' in name:
            return 'plan'
        
        return 'story'  # Default to story

    def _process_artifact(self, file_path: Path) -> None:
        """Processes a single governance artifact file."""
        node_id = self._extract_id_from_filename(file_path)
        if not node_id:
            logger.debug(f"Skipping {file_path}: no valid ID found")
            return

        title = self._extract_title_from_content(file_path)
        node_type = self._determine_node_type(file_path)

        self._add_node(node_id, node_type, title, str(file_path))

        # For runbooks, find the associated story (same ID prefix)
        if node_type == 'runbook':
            # Runbook INFRA-016-runbook.md -> Story INFRA-016
            self._add_edge(source=node_id, target=node_id)  # Self-reference for now
            self._parse_runbook_content(file_path, node_id)

    def _parse_runbook_content(self, file_path: Path, runbook_id: str) -> None:
        """Parses runbook content for file paths to link as code nodes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Regex to find [NEW | MODIFY | DELETE] file/path
            # Match patterns like: [NEW] path/to/file.py or [MODIFY] `path/to/file.py`
            pattern = re.compile(r'\[(?:NEW|MODIFY|DELETE)\]\s+`?([^`\s\[\]]+)`?')
            
            for match in pattern.finditer(content):
                code_path_str = match.group(1).strip()
                
                # Validate it looks like a file path:
                # - Must contain / or .
                # - Should not start with special chars
                # - Should have a file extension
                if not code_path_str:
                    continue
                if code_path_str.startswith(('#', '[', '(')):
                    continue
                if '/' not in code_path_str and '.' not in code_path_str:
                    continue
                if not re.search(r'\.[a-zA-Z0-9]+$', code_path_str):
                    # Doesn't end with file extension - skip
                    continue
                
                # Create a clean node ID from the path (replace special chars with _)
                node_id = re.sub(r'[^a-zA-Z0-9_]', '_', code_path_str)
                self._add_node(
                    node_id=node_id,
                    node_type='code',
                    title=Path(code_path_str).name,
                    path=code_path_str
                )
                self._add_edge(source=runbook_id, target=node_id)

        except Exception as e:
            logger.warning(f"Could not parse content of runbook {file_path}: {e}")

    def build(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scans the repository, builds the graph, and returns it.
        """
        logger.info(f"Starting graph build from root: {self.root_path}")
        
        # Scan each artifact directory
        for artifact_dir, node_type in [
            (self.plans_dir, 'plan'),
            (self.stories_dir, 'story'),
            (self.runbooks_dir, 'runbook'),
        ]:
            if artifact_dir.exists():
                for file_path in artifact_dir.rglob("*.md"):
                    self._process_artifact(file_path)
        
        # Create edges between related artifacts (same ID prefix)
        # Story INFRA-016 -> Runbook INFRA-016
        for node_id, node in list(self.nodes.items()):
            if node['type'] == 'story':
                # Look for matching runbook
                for other_id, other_node in self.nodes.items():
                    if other_node['type'] == 'runbook' and other_id == node_id:
                        self._add_edge(source=node_id, target=other_id)

        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }


def build_from_repo(root_path: str = '.') -> Dict[str, List[Dict[str, Any]]]:
    """
    Factory function to build and return the project graph.
    """
    graph_builder = ProjectGraph(root_path)
    return graph_builder.build()