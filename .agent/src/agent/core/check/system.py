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

"""System health checks: credential validation, story schema, journey linkage.

This module contains check logic that is concerned with *system* health —
whether the local environment, credentials, and story metadata are in a valid
state — distinct from code-quality checks (see quality.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, TypedDict

from agent.core.config import config
from agent.core.logger import get_logger

logger = get_logger(__name__)


def check_credentials(check_llm: bool = False) -> None:
    """Validate that required credentials are present.

    Delegates to :func:`agent.core.auth.credentials.validate_credentials`.
    Raises :class:`agent.core.auth.errors.MissingCredentialsError` on failure.

    Args:
        check_llm: When *True* also verify that at least one LLM provider
            credential is configured.
    """
    from agent.core.auth.credentials import validate_credentials  # ADR-025

    logger.debug("Validating credentials", extra={"check_llm": check_llm})
    validate_credentials(check_llm=check_llm)


class LinkedJourneysResult(TypedDict):
    """Structured return value from :func:`validate_linked_journeys`."""

    passed: bool
    journey_ids: List[str]
    error: Optional[str]


def validate_linked_journeys(story_id: str) -> LinkedJourneysResult:
    """Validate that a story has real linked journeys (not just placeholder JRN-XXX).

    Args:
        story_id: The story identifier, e.g. ``"INFRA-103"``.

    Returns:
        :class:`LinkedJourneysResult` with keys:
            - ``passed`` (bool)
            - ``journey_ids`` (list[str])
            - ``error`` (str | None)
    """
    result: LinkedJourneysResult = {"passed": False, "journey_ids": [], "error": None}

    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break

    if not found_file:
        result["error"] = f"Story file not found for {story_id}"
        logger.debug("Story file not found", extra={"story_id": story_id})
        return result

    content = found_file.read_text(errors="ignore")

    match = re.search(
        r"## Linked Journeys\s*\n(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL,
    )

    if not match:
        result["error"] = "Story is missing '## Linked Journeys' section"
        return result

    section_text = match.group(1).strip()
    if not section_text:
        result["error"] = "Story '## Linked Journeys' section is empty"
        return result

    journey_ids = re.findall(r"\bJRN-\d+\b", section_text)

    if not journey_ids:
        result["error"] = (
            "No valid journey IDs found in '## Linked Journeys' — "
            "replace the JRN-XXX placeholder with real journey IDs"
        )
        return result

    result["passed"] = True
    result["journey_ids"] = journey_ids
    logger.debug(
        "Journey linkage validated",
        extra={"story_id": story_id, "journey_ids": journey_ids},
    )
    return result


class ValidateStoryResult(TypedDict):
    """Structured return value from :func:`validate_story`."""

    passed: bool
    missing_sections: List[str]
    story_file: Optional[str]
    error: Optional[str]


def validate_story(story_id: str) -> ValidateStoryResult:
    """Validate the schema and required sections of a story file.

    Pure data function — no console output, no process control.
    Callers in the ``commands`` layer are responsible for printing
    messages and handling exit codes.

    Args:
        story_id: The story identifier, e.g. ``"INFRA-103"``.

    Returns:
        :class:`ValidateStoryResult` with keys:
            - ``passed`` (bool): True when all required sections are present.
            - ``missing_sections`` (list[str]): Sections absent from the file.
            - ``story_file`` (str | None): Resolved file path, or None if not found.
            - ``error`` (str | None): Human-readable error, or None on success.
    """
    result: ValidateStoryResult = {
        "passed": False,
        "missing_sections": [],
        "story_file": None,
        "error": None,
    }

    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break

    if not found_file:
        result["error"] = f"Story file not found for {story_id}"
        logger.warning("Story file not found", extra={"story_id": story_id})
        return result

    result["story_file"] = str(found_file)
    content = found_file.read_text(errors="ignore")
    required_sections = [
        "Problem Statement",
        "User Story",
        "Acceptance Criteria",
        "Non-Functional Requirements",
        "Impact Analysis Summary",
        "Test Strategy",
        "Rollback Plan",
    ]

    missing = [s for s in required_sections if f"## {s}" not in content]
    result["missing_sections"] = missing

    if missing:
        result["error"] = f"Missing sections: {', '.join(missing)}"
        logger.warning(
            "Story schema validation failed",
            extra={"story_id": story_id, "missing_sections": missing},
        )
        return result

    result["passed"] = True
    logger.info("Story schema validation passed", extra={"story_id": story_id})
    return result