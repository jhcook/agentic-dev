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

from backend.voice.events import EventBus
from backend.voice.process_manager import ProcessLifecycleManager
from agent.core.config import config as agent_config
import subprocess
import threading
import time
from agent.core.utils import sanitize_id


def _run_interactive_command(command: str, alias_prefix: str, session_id: str, start_message: str) -> str:
    """
    Helper to run an interactive shell command with process management and event streaming.
    """
    process_id = f"{alias_prefix}-{int(time.time())}"

    EventBus.publish(session_id, "console", f"> Executing: {command} (ID: {process_id})\n")

    try:
        # Wrap with source activation
        full_command = f"source .venv/bin/activate && {command}"

        process = subprocess.Popen(
            full_command,
            shell=True,
            executable='/bin/zsh',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(agent_config.repo_root)
        )

        ProcessLifecycleManager.instance().register(process, process_id)

        def read_output():
            try:
                for line in iter(process.stdout.readline, ''):
                    EventBus.publish(session_id, "console", f"[{process_id}] {line}")

                process.stdout.close()
                rc = process.wait()

                status = "Completed" if rc == 0 else f"Failed (Code {rc})"
                EventBus.publish(session_id, "console", f"\n[{process_id}] {status}.\n")

            except Exception as e:
                EventBus.publish(session_id, "console", f"[{process_id}] Error: {e}")
            finally:
                ProcessLifecycleManager.instance().unregister(process_id)

        t = threading.Thread(target=read_output, daemon=True)
        t.start()

        return start_message

    except Exception as e:
        return f"Failed to start {alias_prefix}: {e}"

def run_new_story(story_id: str = None, session_id: str = "unknown") -> str:
    """
    Create a new user story.
    Args:
        story_id: Optional ID (e.g. 'WEB-001'). If not provided, it will be generated.
    """
    cmd = "agent new-story"
    if story_id:
        clean_id = sanitize_id(story_id)
        cmd += f" {clean_id}"
    return _run_interactive_command(cmd, "story", session_id, "Story creation started. Follow along below.")

def run_new_runbook(story_id: str, session_id: str = "unknown") -> str:
    """
    Generate an implementation runbook for a story.
    Args:
        story_id: The ID of the committed story (e.g., 'WEB-001').
    """
    clean_id = sanitize_id(story_id)
    cmd = f"agent new-runbook {clean_id}"
    return _run_interactive_command(cmd, "runbook", session_id, "Runbook generation started. Follow along below.")

def run_implement(runbook_id: str, session_id: str = "unknown") -> str:
    """
    Implement a feature from an accepted runbook.
    Args:
        runbook_id: The ID of the accepted runbook (e.g., 'WEB-001').
    """
    clean_id = sanitize_id(runbook_id)
    # Always apply changes when implementing via voice
    cmd = f"agent implement {clean_id} --apply"
    return _run_interactive_command(cmd, "implement", session_id, "Implementation started (with --apply). Follow along below.")

def run_impact(files: str = None, session_id: str = "unknown") -> str:
    """
    Run impact analysis on files.
    Args:
        files: Space-separated list of files to analyze (default: staged changes).
    """
    cmd = "agent impact"
    if files:
        cmd += f" --files {files}"
    else:
        cmd += " --staged"

    return _run_interactive_command(cmd, "impact", session_id, "Impact analysis started. Follow along below.")

def run_panel(question: str, apply_advice: bool = False, session_id: str = "unknown") -> str:
    """
    Consult the AI Governance Panel.
    Args:
        question: The question or design decision to review.
        apply_advice: If True, automatically updates the Story/Runbook with the panel's advice.
    """
    # Escape quotes
    safe_q = question.replace('"', '\\"')
    cmd = f'agent panel "{safe_q}"'
    if apply_advice:
        cmd += " --apply"
    return _run_interactive_command(cmd, "panel", session_id, "Governance panel convened. Follow along below.")

def run_review_voice(session_id: str = "unknown") -> str:
    """
    Review a voice session for UX improvements.
    Args:
        session_id: Optional session ID to review. Defaults to latest.
    """
    cmd = "agent review-voice"
    if session_id and session_id != "unknown":
        cmd += f" {session_id}"
    return _run_interactive_command(cmd, "review", session_id, "Voice review started. Follow along below.")
