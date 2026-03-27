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

"""Deterministic complexity analysis engine using AST (ADR-012)."""

import ast
from dataclasses import dataclass
from typing import List


@dataclass
class FunctionMetrics:
    """Metrics for an individual function or method."""
    name: str
    length: int
    lineno: int
    verdict: str  # PASS, WARN, BLOCK


@dataclass
class ComplexityReport:
    """Aggregate complexity metrics for a file."""
    total_loc: int
    file_verdict: str
    functions: List[FunctionMetrics]


def get_complexity_report(content: str, filename: str = "unknown") -> ComplexityReport:
    """Walk the Python AST and calculate deterministic metrics.

    Enforces thresholds:
    - File: > 500 LOC (WARN)
    - Function: 21-50 lines (WARN), > 50 lines (BLOCK)
    """
    lines = content.splitlines()
    total_loc = len(lines)
    file_verdict = "PASS"
    if total_loc > 500:
        file_verdict = "WARN"

    functions = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate length excluding leading docstrings or comments if possible
                # For simplicity, we use end_lineno - lineno + 1
                length = (getattr(node, "end_lineno", node.lineno) - node.lineno) + 1
                
                verdict = "PASS"
                if length > 50:
                    verdict = "BLOCK"
                elif length > 20:
                    verdict = "WARN"
                
                functions.append(FunctionMetrics(
                    name=node.name,
                    length=length,
                    lineno=node.lineno,
                    verdict=verdict
                ))
    except SyntaxError:
        # If the file doesn't parse, we can't perform function analysis
        pass

    return ComplexityReport(
        total_loc=total_loc,
        file_verdict=file_verdict,
        functions=functions
    )
