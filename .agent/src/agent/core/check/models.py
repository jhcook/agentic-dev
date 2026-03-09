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
from agent.core.check.quality import JourneyCoverageResult
from agent.core.check.system import ValidateStoryResult

class AffectedJourney(TypedDict):
    """A journey affected by changes."""
    id: str
    tests: List[str]
    matched_files: List[str]

class TestCommand(TypedDict):
    """A command to execute tests."""
    name: str
    cmd: List[str]
    cwd: Any

class RebuildIndexResult(TypedDict):
    """Result of a journey index rebuild."""
    journey_count: int
    file_glob_count: int

class ImpactResult(TypedDict):
    """Result of an impact analysis operation."""
    story_id: str
    impact_summary: str
    changed_files: List[str]
    reverse_dependencies: Dict[str, List[str]]
    risk_assessment: str
    tokens_used: int
    is_offline: bool
    components: set[str]
    total_impacted: int
    affected_journeys: List[AffectedJourney]
    test_markers: List[str]
    ungoverned_files: List[str]
    rebuild_result: Optional[RebuildIndexResult]
    story_updated: bool
    story_file_name: Optional[str]
    error: Optional[str]

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
    system_validation: ValidateStoryResult
    quality_metrics: JourneyCoverageResult
    timestamp: str

class SyncOraclePatternResult(TypedDict):
    """Result of the Oracle Pattern synchronization."""
    notebooklm_ready: bool
    notebooklm_status: str
    notion_ready: bool
    notion_status: str
    vector_db_ready: bool
    vector_db_status: str

class SmartTestSelectionResult(TypedDict):
    """Result of the smart test selection process."""
    passed: bool
    skipped: bool
    test_commands: List[TestCommand]
    ignored: bool
    error: Optional[str]

class JourneyCoverageGateResult(TypedDict):
    """Result of the journey coverage gate check."""
    passed: bool
    warnings: List[str]
    missing_ids: set[str]
    linked: int
    total: int
    error: Optional[str]

class JourneyImpactMappingResult(TypedDict):
    """Result of journey impact mapping."""
    affected_journeys: List[AffectedJourney]
    changed_files: List[str]
    rebuilt_index: bool
    test_files_to_run: List[str]