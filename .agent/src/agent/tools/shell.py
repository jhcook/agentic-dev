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
Shell tools for agentic workflows.

Provides operations for executing commands and managing interactive sessions.
All commands are sandboxed to the repository root.
"""

import logging
import os
import shlex
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, TypedDict

from opentelemetry import trace

from agent.core.utils import scrub_sensitive_data
from agent.tools.utils import validate_path

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Re-export the shared helper under the legacy private name so that any
# internal callers within this module continue to work unchanged.
_validate_path = validate_path


class BackgroundProcessState(TypedDict):
    """Represents the state of a background process."""
    proc: subprocess.Popen
    command: str
    output_buffer: List[str]


_BACKGROUND_PROCESSES: Dict[str, BackgroundProcessState] = {}


def run_command(
    command: str,
    repo_root: Path,
    background: bool = False,
    on_output: Optional[Callable[[str], None]] = None
) -> str:
    """
    Executes a shell command in the repository root.

    Args:
        command: The command to execute.
        repo_root: Repository root path.
        background: Whether to run in the background.
        on_output: Callback for streaming output.

    Returns:
        Command output or ID.
    """
    with tracer.start_as_current_span("tool.run_command") as span:
        span.set_attribute("tool.command", command)
        span.set_attribute("tool.background", background)
        try:
            if not command.strip():
                return "Error: empty command."
            if ".." in command:
                return "Error: path traversal ('..') is not allowed."

            for token in shlex.split(command):
                if token.startswith("/"):
                    _validate_path(token, repo_root)

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            args = shlex.split(command)

            proc = subprocess.Popen(
                args,
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if background else None,
                text=True,
                shell=False,
                bufsize=1,
            )

            if background:
                cmd_id = str(uuid.uuid4())
                state: BackgroundProcessState = {
                    "proc": proc,
                    "command": command,
                    "output_buffer": []
                }
                _BACKGROUND_PROCESSES[cmd_id] = state

                def _read_output():
                    if proc.stdout:
                        for line in iter(proc.stdout.readline, ''):
                            stripped = line.rstrip("\n")
                            state["output_buffer"].append(stripped)
                            if len(state["output_buffer"]) > 200:
                                state["output_buffer"].pop(0)
                            if on_output:
                                on_output(stripped)

                threading.Thread(target=_read_output, daemon=True).start()
                return f"Command started with ID: {cmd_id}"

            output_captured = []
            if proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    stripped = line.rstrip("\n")
                    output_captured.append(stripped)
                    if on_output:
                        on_output(stripped)

            proc.wait(timeout=120)
            output_text = scrub_sensitive_data("\n".join(output_captured[-50:]))
            return output_text or f"Exited with code {proc.returncode}"

        except Exception as e:
            span.record_exception(e)
            return f"Error: {e}"


def send_command_input(command_id: str, input_text: str) -> str:
    """
    Sends input to a background process.

    Args:
        command_id: The ID returned by ``run_command`` when ``background=True``.
        input_text: Text to write to the process's stdin.

    Returns:
        Confirmation or error message.
    """
    with tracer.start_as_current_span("tool.send_command_input") as span:
        span.set_attribute("tool.command_id", command_id)
        state = _BACKGROUND_PROCESSES.get(command_id)
        if not state:
            return "Error: Process not found."
        proc = state["proc"]
        if proc.poll() is not None:
            return f"Error: Process exited with {proc.returncode}"
        try:
            if proc.stdin:
                if not input_text.endswith('\n'):
                    input_text += '\n'
                proc.stdin.write(input_text)
                proc.stdin.flush()
                return "Input sent."
            return "Error: stdin unavailable."
        except Exception as e:
            span.record_exception(e)
            return f"Error: {e}"


def check_command_status(command_id: str) -> str:
    """
    Checks the status of a background process.

    Args:
        command_id: The ID returned by ``run_command`` when ``background=True``.

    Returns:
        Status string with recent output.
    """
    with tracer.start_as_current_span("tool.check_command_status") as span:
        span.set_attribute("tool.command_id", command_id)
        state = _BACKGROUND_PROCESSES.get(command_id)
        if not state:
            return "Error: Process not found."
        proc = state["proc"]
        status = "Running" if proc.poll() is None else f"Exited: {proc.returncode}"
        output = scrub_sensitive_data("\n".join(state["output_buffer"][-50:]))
        return f"Status: {status}\nRecent Output:\n{output}"


def interactive_shell(repo_root: Path) -> str:
    """
    Starts an interactive shell session (stub).

    Args:
        repo_root: Repository root path.

    Returns:
        Session description.
    """
    with tracer.start_as_current_span("tool.interactive_shell"):
        return "Interactive shell not supported in non-TTY mode."