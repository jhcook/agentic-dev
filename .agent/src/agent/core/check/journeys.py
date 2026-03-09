# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0 (the "License");

import subprocess
import sqlite3
from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.check.models import JourneyCoverageGateResult, JourneyImpactMappingResult
from agent.core.check.system import ValidateStoryResult
from opentelemetry import trace

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

def check_journey_coverage_gate(journey_gate: ValidateStoryResult) -> JourneyCoverageGateResult:
    """Run Phase 2 of Journey Coverage Check (Blocking for story-linked journeys).
    
    Ensures that any journey linked under the story's "Linked Journeys" section
    actually has automated tests correctly linked and implemented. Overlap between
    untested journeys (missing_ids) and the requested story triggers a BLOCK.
    
    Args:
        journey_gate: A previous validation result containing journey IDs from the story.
        
    Returns:
        JourneyCoverageGateResult containing pass/fail state and detailed blockage information.
    """
    with tracer.start_as_current_span("check_journey_coverage_gate"):
        from agent.core.check.quality import check_journey_coverage
        
        coverage_result = check_journey_coverage()
    
    result: JourneyCoverageGateResult = {
        "passed": True,
        "warnings": coverage_result.get("warnings", []),
        "missing_ids": set(),
        "linked": coverage_result.get("linked", 0),
        "total": coverage_result.get("total", 0),
        "error": None
    }

    if result["warnings"]:
        story_journey_ids = set(journey_gate.get("journey_ids", []))
        missing_ids = set(coverage_result.get("missing_ids", []))
        blocked_journeys = story_journey_ids & missing_ids

        if blocked_journeys:
            result["passed"] = False
            result["missing_ids"] = blocked_journeys
            result["error"] = (
                f"Journey Test Coverage FAILED — story-linked journey(s) "
                f"{', '.join(sorted(blocked_journeys))} have no tests. "
                f"Add tests to implementation.tests in each journey YAML."
            )

    return result


def run_journey_impact_mapping(base: str | None) -> JourneyImpactMappingResult:
    """Map changed files to journeys (INFRA-059).
    
    Correlates the given git diff (against `base` or index) against the journey
    graph, determining which journeys and their corresponding tests are impacted.
    
    Args:
        base: The base reference to diff against (e.g., "main"). If None, diffs cached files.
        
    Returns:
        JourneyImpactMappingResult containing affected journeys and tests to run.
    """
    with tracer.start_as_current_span("run_journey_impact_mapping"):
        from agent.db.journey_index import (
            get_affected_journeys as _get_affected,
            is_stale as _is_stale,
            rebuild_index as _rebuild_idx,
        )
        from agent.db.init import get_db_path as _get_db_path

    _db = sqlite3.connect(_get_db_path())
    _journeys_dir = config.journeys_dir
    _repo_root = config.repo_root

    result: JourneyImpactMappingResult = {
        "affected_journeys": [],
        "changed_files": [],
        "rebuilt_index": False,
        "test_files_to_run": []
    }

    if _is_stale(_db, _journeys_dir):
        _idx = _rebuild_idx(_db, _journeys_dir, _repo_root)
        logger.info("Rebuilt journey index", extra={"index": _idx})
        result["rebuilt_index"] = True

    _pf_cmd = (
        ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
        if base
        else ["git", "diff", "--cached", "--name-only"]
    )
    try:
        _pf_res = subprocess.run(_pf_cmd, capture_output=True, text=True)
        _pf_files = _pf_res.stdout.strip().splitlines()
        _pf_files = [f for f in _pf_files if f]
    except Exception as e:
        logger.error("Failed to get git diff", extra={"error": str(e)})
        _pf_files = []
        
    result["changed_files"] = _pf_files

    if _pf_files:
        _affected = _get_affected(_db, _pf_files, _repo_root)
        if _affected:
            result["affected_journeys"] = _affected
            _test_files: list[str] = []
            for _j in _affected:
                _test_files.extend(_j.get("tests", []))
            
            if _test_files:
                result["test_files_to_run"] = sorted(set(_test_files))

    _db.close()
    return result
