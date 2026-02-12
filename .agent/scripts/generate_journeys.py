#!/usr/bin/env python3
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
Batch-generate user journey YAML files from existing runbooks.

Each runbook maps to one journey. The journey captures the developer-facing
CLI interaction described by the runbook.

Usage:
    python3 .agent/scripts/generate_journeys.py
    python3 .agent/scripts/generate_journeys.py --start-num 52  # Continue numbering from JRN-052
    python3 .agent/scripts/generate_journeys.py --dry-run       # Preview without writing
"""

import argparse
import os
import re
from pathlib import Path

import yaml

# Resolve paths relative to the repo root (two levels up from this script)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
RUNBOOK_DIR = REPO_ROOT / ".agent" / "cache" / "runbooks"
JOURNEY_DIR = REPO_ROOT / ".agent" / "cache" / "journeys"


def sanitize_title(title: str) -> str:
    """Convert title to safe filename component."""
    title = re.sub(r'[^\w\s-]', '', title.lower())
    title = re.sub(r'[\s]+', '-', title.strip())
    return title[:60]


def extract_runbook_info(path: Path) -> dict:
    """Extract structured info from a runbook markdown file."""
    content = path.read_text()

    # Extract story ID from filename
    id_match = re.search(r'((?:INFRA|WEB|MOBILE)-\d+)', path.name)
    story_id = id_match.group(1) if id_match else path.stem

    # Extract scope from directory
    scope = path.parent.name  # INFRA, WEB, MOBILE

    # Extract title
    title_match = re.search(r'^#\s+(?:STORY-?ID:\s*)?(.+)', content, re.MULTILINE)
    raw_title = title_match.group(1).strip() if title_match else story_id
    # Clean title - remove story ID prefix
    clean_title = re.sub(r'^(?:STORY-?ID:\s*)?(?:INFRA|WEB|MOBILE)-\d+[\s:]*', '', raw_title).strip()
    if not clean_title or clean_title == path.stem:
        clean_title = raw_title

    # Extract goal/description
    goal = ""
    goal_patterns = [
        r'##\s+Goal\s*(?:Description)?\s*\n\n(.+?)(?:\n\n##|\n##)',
        r'##\s+Goal\s*(?:Description)?\s*\n\n(.+?)$',
        r'##\s+Goal\s*\n(.+?)(?:\n##)',
    ]
    for pat in goal_patterns:
        goal_match = re.search(pat, content, re.DOTALL)
        if goal_match:
            goal = goal_match.group(1).strip()
            # Take first paragraph
            goal = goal.split('\n\n')[0].strip()
            break

    if not goal:
        # Fallback: use first paragraph after title
        para_match = re.search(r'^#.+\n\n(?:##\s+\w+\s*\n\n)?(.+?)(?:\n\n)', content, re.DOTALL)
        if para_match:
            goal = para_match.group(1).strip()

    # Extract key commands mentioned
    commands = set()
    cmd_pattern = re.compile(r'`(agent\s+\w[\w\s-]*)`')
    for m in cmd_pattern.finditer(content):
        commands.add(m.group(1).strip())

    # Extract key files mentioned
    files = set()
    file_pattern = re.compile(r'`([a-zA-Z_/]+\.(?:py|ts|tsx|md|yaml|json))`')
    for m in file_pattern.finditer(content):
        files.add(m.group(1))

    # Detect interaction category
    content_lower = content.lower()
    category = "cli"
    if "websocket" in content_lower or "voice" in content_lower or "stt" in content_lower or "tts" in content_lower:
        category = "voice"
    elif "react" in content_lower and ("component" in content_lower or "dashboard" in content_lower or "ui" in content_lower):
        category = "web_ui"
    elif "mobile" in content_lower and "ios" in content_lower:
        category = "mobile"
    elif any(cmd in content_lower for cmd in [
        "agent onboard", "agent config", "agent audit", "agent query",
        "agent list", "agent commit", "agent sync", "agent preflight",
        "agent implement", "agent new-"
    ]):
        category = "cli"

    return {
        "story_id": story_id,
        "scope": scope,
        "title": clean_title,
        "goal": goal,
        "commands": sorted(commands),
        "files": sorted(files)[:10],
        "category": category,
        "full_content": content,
    }


def determine_actor(info: dict) -> str:
    """Determine the actor based on category."""
    if info["category"] == "voice":
        return "developer using voice assistant"
    elif info["category"] == "web_ui":
        return "developer using admin console"
    elif info["category"] == "mobile":
        return "mobile developer"
    else:
        return "developer using agent CLI"


def generate_steps_from_runbook(info: dict) -> list:
    """Generate journey steps from runbook info."""
    content = info["full_content"]
    steps = []

    # Try to extract phases/steps from the runbook
    phase_pattern = re.compile(
        r'###?\s+(?:Phase\s+\d+|Step\s+\d+|Stage\s+\d+)[:\s]+(.+?)(?=\n###?\s|\n##\s|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    phases = phase_pattern.findall(content)

    if phases:
        for i, phase in enumerate(phases[:6], 1):
            phase_title = phase.split('\n')[0].strip()
            steps.append({
                "id": i,
                "action": f"Developer initiates phase: {phase_title}",
                "system_response": f"System executes {phase_title.lower()}",
                "assertions": [f"{phase_title} completes successfully"],
            })
    else:
        # Generate steps based on detected commands
        if info["commands"]:
            for i, cmd in enumerate(info["commands"][:5], 1):
                steps.append({
                    "id": i,
                    "action": f"Developer runs `{cmd}`",
                    "system_response": f"CLI processes the {cmd.split()[-1] if len(cmd.split()) > 1 else cmd} request",
                    "assertions": ["Command exits with status 0", "Expected output displayed"],
                })

    # Ensure at least basic steps
    if not steps:
        goal_short = info["goal"][:80] if info["goal"] else info["title"]
        if info["category"] == "web_ui":
            steps = [
                {"id": 1, "action": "Developer starts admin console with `agent admin start`",
                 "system_response": "Frontend (5173) and backend (8000) start",
                 "assertions": ["Console is accessible at http://localhost:5173"]},
                {"id": 2, "action": f"Developer navigates to feature: {info['title']}",
                 "system_response": f"UI renders {info['title']} view",
                 "assertions": ["View loads without errors", "Data is displayed correctly"]},
                {"id": 3, "action": "Developer interacts with the feature",
                 "system_response": "System processes the interaction and updates state",
                 "assertions": ["Changes are persisted", "UI feedback is immediate"]},
            ]
        elif info["category"] == "voice":
            steps = [
                {"id": 1, "action": "Developer starts voice session via WebSocket or admin console",
                 "system_response": "Voice agent initializes STT/TTS pipeline",
                 "assertions": ["WebSocket connection established", "Audio pipeline ready"]},
                {"id": 2, "action": "Developer speaks a command or question",
                 "system_response": "System transcribes speech, processes intent, generates response",
                 "assertions": ["Transcription is accurate", "Response is relevant"]},
                {"id": 3, "action": "Developer receives spoken response",
                 "system_response": "TTS converts response to speech, streams audio back",
                 "assertions": ["Audio plays clearly", "Latency is acceptable"]},
            ]
        else:
            steps = [
                {"id": 1, "action": f"Developer configures prerequisites for {info['title']}",
                 "system_response": "System validates configuration",
                 "assertions": ["Configuration is valid"]},
                {"id": 2, "action": f"Developer executes the {info['title'].lower()} workflow",
                 "system_response": f"System performs {goal_short.lower()}",
                 "assertions": ["Operation completes successfully", "Output matches expectations"]},
                {"id": 3, "action": "Developer verifies the result",
                 "system_response": "System displays confirmation or results",
                 "assertions": ["Expected artifacts created", "No errors reported"]},
            ]

    return steps


def generate_journey(jrn_num: int, info: dict) -> tuple:
    """Generate a complete journey dict."""
    journey_id = f"JRN-{jrn_num:03d}"
    actor = determine_actor(info)
    steps = generate_steps_from_runbook(info)

    journey = {
        "id": journey_id,
        "title": info["title"],
        "state": "COMMITTED",
        "schema_version": 1,
        "priority": "medium",
        "tags": [info["scope"].lower(), info["category"]],
        "actor": actor,
        "description": info["goal"][:500] if info["goal"] else f"Developer uses {info['title']}",
        "preconditions": ["Agent CLI is installed and configured", "Developer is in a project directory with .agent/ initialized"],
        "auth_context": {
            "level": "authenticated" if any(kw in info["full_content"].lower() for kw in ["api key", "credential", "secret", "token"]) else "public",
            "permissions": [],
        },
        "steps": steps,
        "error_paths": [
            {
                "trigger_step": 1,
                "condition": "Missing configuration or prerequisites",
                "system_response": "CLI displays clear error with remediation steps",
                "assertions": ["Error message is actionable"],
                "severity": "expected",
            }
        ],
        "edge_cases": [
            {
                "scenario": "Command run with no network access",
                "expected": "Graceful degradation or clear offline error",
                "severity": "warning",
            }
        ],
        "data_state": {
            "data_classification": "internal",
            "inputs": [],
            "persistent": [],
        },
        "linked_stories": [info["story_id"]],
        "linked_adrs": [],
        "depends_on": [],
        "implementation": {
            "routes": [],
            "files": list(info["files"])[:5],
            "tests": [],
        },
    }

    return journey_id, journey


def get_existing_journey_ids() -> set:
    """Return the set of JRN-NNN IDs already on disk."""
    existing = set()
    if JOURNEY_DIR.exists():
        for root, _, files in os.walk(JOURNEY_DIR):
            for f in files:
                m = re.match(r'(JRN-\d+)', f)
                if m:
                    existing.add(m.group(1))
    return existing


def main():
    parser = argparse.ArgumentParser(description="Generate journey YAML files from runbooks.")
    parser.add_argument("--start-num", type=int, default=1, help="Starting JRN number (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--skip-existing", action="store_true", help="Skip runbooks that already have a journey")
    args = parser.parse_args()

    # Collect all runbooks
    runbooks = []
    for root, dirs, files in sorted(os.walk(RUNBOOK_DIR)):
        for f in sorted(files):
            if f.endswith('-runbook.md'):
                runbooks.append(Path(root) / f)

    print(f"Found {len(runbooks)} runbooks")

    existing_ids = get_existing_journey_ids()
    if existing_ids:
        print(f"Found {len(existing_ids)} existing journeys on disk")

    # Generate journeys
    created = 0
    skipped = 0
    for i, rb_path in enumerate(runbooks, args.start_num):
        info = extract_runbook_info(rb_path)

        # Check if a journey already exists for this story
        if args.skip_existing:
            already_has = any(
                info["story_id"].lower() in (JOURNEY_DIR / root / f).read_text().lower()
                for root, _, files in os.walk(JOURNEY_DIR) if JOURNEY_DIR.exists()
                for f in files if f.endswith('.yaml')
            )
            if already_has:
                skipped += 1
                continue

        jrn_id, journey = generate_journey(i, info)

        # Create scope directory
        scope_dir = JOURNEY_DIR / info["scope"]
        scope_dir.mkdir(parents=True, exist_ok=True)

        # Write YAML
        safe_title = sanitize_title(journey["title"])
        filename = f"{jrn_id}-{safe_title}.yaml"
        out_path = scope_dir / filename

        if args.dry_run:
            print(f"  [DRY-RUN] {jrn_id} -> {out_path.relative_to(JOURNEY_DIR)}")
        else:
            with open(out_path, 'w') as f:
                f.write(f"# Journey: {jrn_id}\n")
                f.write(f"# Linked Story: {info['story_id']}\n")
                f.write(f"# Title: {journey['title']}\n\n")
                yaml.dump(journey, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)
            print(f"  ✅ {jrn_id} -> {out_path.relative_to(JOURNEY_DIR)}")

        created += 1

    print(f"\n{'Would create' if args.dry_run else 'Generated'} {created} journeys in {JOURNEY_DIR}")
    if skipped:
        print(f"Skipped {skipped} (already had journeys)")


if __name__ == "__main__":
    main()
