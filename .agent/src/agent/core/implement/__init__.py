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

"""Public API for the core implement package.

Re-exports the symbols that external callers (including the CLI facade
and existing test files) depend on, so import paths are stable across
the decomposition.
"""

from agent.core.implement.circuit_breaker import (
    CircuitBreaker,
    count_edit_distance,
    create_follow_up_story,
    update_or_create_plan,
    micro_commit_step,
    MAX_EDIT_DISTANCE_PER_STEP,
    LOC_WARNING_THRESHOLD,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
)
from agent.core.implement.guards import (
    enforce_docstrings,
    apply_change_to_file,
    apply_search_replace_to_file,
    backup_file,
    FILE_SIZE_GUARD_THRESHOLD,
)
from agent.core.implement.orchestrator import (
    Orchestrator,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
)

__all__ = [
    "CircuitBreaker",
    "Orchestrator",
    "count_edit_distance",
    "create_follow_up_story",
    "update_or_create_plan",
    "micro_commit_step",
    "enforce_docstrings",
    "apply_change_to_file",
    "apply_search_replace_to_file",
    "backup_file",
    "parse_code_blocks",
    "parse_search_replace_blocks",
    "split_runbook_into_chunks",
    "MAX_EDIT_DISTANCE_PER_STEP",
    "LOC_WARNING_THRESHOLD",
    "LOC_CIRCUIT_BREAKER_THRESHOLD",
    "FILE_SIZE_GUARD_THRESHOLD",
]