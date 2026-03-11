#!/usr/bin/env python3
"""
Copyright 2026 Justin Cook
License: Apache-2.0
Detect circular dependencies using static AST analysis.
"""
import ast
import sys
from pathlib import Path
from typing import Dict, Set, List, Optional

def get_imports(path: Path) -> Set[str]:
    """Extract imported module names using AST analysis."""
    imports = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])
    except Exception:
        pass
    return imports

def find_cycle(graph: Dict[str, Set[str]]) -> Optional[List[str]]:
    """Detect circular dependencies in the dependency graph."""
    visited: Set[str] = set()
    path: List[str] = []
    
    def visit(node: str) -> Optional[List[str]]:
        """DFS recursive visit to find cycles."""
        if node in path:
            return path[path.index(node):] + [node]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            res = visit(neighbor)
            if res: return res
        path.pop()
        return None

    for node in graph:
        res = visit(node)
        if res: return res
    return None

def main():
    """Build dependency graph and report if a cycle is found."""
    root = Path(".agent/src/agent")
    if not root.exists():
        root = Path("src/agent")
        
    graph = {}
    for p in root.rglob("*.py"):
        mod = p.stem
        graph[mod] = get_imports(p)
    
    cycle = find_cycle(graph)
    if cycle:
        print(f"FAIL: Circular dependency detected: {' -> '.join(cycle)}")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
