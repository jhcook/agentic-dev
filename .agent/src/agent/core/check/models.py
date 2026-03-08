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

"""
Data models for check operations.
"""

from typing import Any, Dict, List, Optional, TypedDict

class ImpactResult(TypedDict):
    """Result of an impact analysis operation."""
    story_id: str
    impact_summary: str
    changed_files: List[str]
    reverse_dependencies: Dict[str, List[str]]
    risk_assessment: str
    tokens_used: int

class RoleVerdict(TypedDict):
    """Verdict from a specific governance council role."""
    role: str
    verdict: str  # PASS, BLOCK, NEUTRAL
    findings: List[str]
    citations: List[str]

class PreflightResult(TypedDict):
    """Consolidated result of a preflight check sequence."""
    story_id: str
    success: bool
    verdicts: List[RoleVerdict]
    impact: ImpactResult
    system_validation: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    timestamp: str