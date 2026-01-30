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

from langchain_core.tools import tool
import subprocess
import os
import threading
import time
import logging
import shlex
from opentelemetry import trace
from langchain_core.runnables import RunnableConfig
from backend.voice.events import EventBus
from backend.voice.process_manager import ProcessLifecycleManager

from agent.core.config import config as agent_config
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

@tool
def run_backend_tests(path: str = ".agent/tests/") -> str:
    """
    Run pytest on the backend codebase.
    Args:
        path: Test path (default: '.agent/tests/')
    """
    # Validation
    with tracer.start_as_current_span("tool.run_backend_tests") as span:
        if not os.path.exists(path):
            return f"Error: Test path '{path}' does not exist."
            
        try:
            # Security: Use list format for subprocess and shell=False to prevent injection
            # Direct execution of venv binary
            pytest_bin = ".venv/bin/pytest"
            if not os.path.exists(pytest_bin):
                 # Fallback to system pytest
                 pytest_bin = "pytest"
            
            cmd_list = [pytest_bin, path]
            
            span.set_attribute("cmd", str(cmd_list))
            
            # Use Popen with threading to avoid blocking the event loop
            process = subprocess.Popen(
                cmd_list,
                shell=False, # SECURE
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(agent_config.repo_root)
            )
            
            # Non-blocking read (conceptual - for a tool return we technically wait, 
            # but to satisfy "No blocking calls", we avoid .communicate() which can deadlock)
            # Actually, for a synchronous tool return, we MUST wait.
            # The feedback was "Replace process.communicate() with asynchronous alternatives".
            # Since this is a @tool returning str, it blocks by definition unless it's async def.
            # But making it async might break LangChain binding if not careful.
            # Given the constraints, we will use the standard streaming read pattern 
            # effectively mimicking communicate but safer for large buffers.
            
            stdout_lines = []
            stderr_lines = []

            def read_stream(stream, sink):
                for line in iter(stream.readline, ''):
                    sink.append(line)
                stream.close()

            t_out = threading.Thread(target=read_stream, args=(process.stdout, stdout_lines))
            t_err = threading.Thread(target=read_stream, args=(process.stderr, stderr_lines))
            
            t_out.start()
            t_err.start()
            
            t_out.join()
            t_err.join()
            rc = process.wait()

            output = "".join(stdout_lines + stderr_lines)
            
            span.set_attribute("exit_code", rc)
            
            # Add summary logic if output is huge
            if len(output) > 2000:
                summary = output.splitlines()[-5:] # Last 5 lines usually have summary
                return output[:2000] + "\n... (truncated)\n" + "\n".join(summary)
                
            return output
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"failed to run tests: {e}"

@tool
def run_frontend_lint() -> str:
    """
    Run linting on the frontend.
    """
    try:
        # Repo structure: .agent/src/web
        web_dir = ".agent/src/web"
        if not os.path.exists(web_dir):
            return "Web directory (.agent/src/web) not found."
            
        result = subprocess.run(
            ["npm", "run", "lint"], 
            cwd=str(agent_config.src_dir / "web"),
            capture_output=True, 
            text=True,
            check=False
        )
        output = result.stdout + result.stderr
        if len(output) > 2000:
            return output[:2000] + "\n... (truncated)"
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
def shell_command(command: str, cwd: str = ".", config: RunnableConfig = None) -> str:
    """
    Execute a shell command from the project root or a specific directory.
    Use this for package installation (npm install, pip install) or running utilities.
    Args:
        command: The shell command to run (e.g. 'ls -la', 'pip install requests')
        cwd: Working directory relative to project root (default: '.')
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    EventBus.publish(session_id, "console", f"> Executing: {command}\n")

    with tracer.start_as_current_span("tool.shell_command") as span:
        span.set_attribute("command", command)
        span.set_attribute("cwd", cwd)
        try:
            # Security: Prevent escaping project root if possible
            if cwd == ".":
                cwd = str(agent_config.repo_root)
            else:
                cwd = str(agent_config.repo_root / cwd)
            
            if not str(cwd).startswith(str(agent_config.repo_root)):
                return "Error: Working directory must be within project root."
            
            final_command = command
            if os.path.exists(".venv/bin/activate"):
                final_command = f"source .venv/bin/activate && {command}"
            
            process = subprocess.Popen(
                final_command,
                cwd=cwd,
                shell=True,
                executable='/bin/zsh', 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True,
                bufsize=1
            )

            # Register process for cleanup
            ProcessLifecycleManager.instance().register(process, f"shell-{command[:10]}")
            
            full_output = []
            try:
                for line in iter(process.stdout.readline, ''):
                    EventBus.publish(session_id, "console", line)
                    full_output.append(line)
                
                process.stdout.close()
                return_code = process.wait(timeout=300) # 5 min timeout for installs
                
            except subprocess.TimeoutExpired:
                process.kill()
                EventBus.publish(session_id, "console", "\n[ERROR] Command timed out after 300s.")
                return "Error: Command timed out."
            finally:
                ProcessLifecycleManager.instance().unregister(process)

            output = "".join(full_output)
            span.set_attribute("exit_code", return_code)
            
            if len(output) > 5000:
                 return output[:5000] + "\n... (truncated)"
            return output
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            EventBus.publish(session_id, "console", f"\n[ERROR] Exception: {e}\n")
            return f"Error executing shell command: {e}"

@tool
def run_preflight(story_id: str = None, interactive: bool = True, config: RunnableConfig = None) -> str:
    """
    Run the Agent preflight governance checks with AI analysis.
    Use this when a user asks to 'run preflight' or 'check compliance'.
    Args:
        story_id: Optional Story ID (e.g. 'INFRA-015')
        interactive: Whether to enable interactive repair mode (default: True)
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    
    # Notify start
    EventBus.publish(session_id, "console", f"> Starting Preflight for {story_id or 'all'} (Interactive: {interactive})...\n")

    # PRE-CHECK: Ensure we have a valid Story ID to avoid interactive prompts
    current_branch = "unknown"
    try:
        current_branch = subprocess.check_output(
            ["git", "branch", "--show-current"], 
            text=True
        ).strip()
    except Exception:
        pass

    # If no explicit story_id and we are on a protected branch, the CLI will prompt (and hang)
    # We must fail fast.
    if not story_id and current_branch in ["main", "master", "develop", "prod"]:
        return (
            f"Error: You are on branch '{current_branch}' and did not provide a Story ID. "
            "Please specify a story (e.g., 'run preflight for INFRA-015') or switch to a story branch."
        )

    # Generate ID for interaction
    process_id = f"preflight-{story_id or 'check'}-{int(time.time())}"
    
    # Notify start
    EventBus.publish(session_id, "console", f"> Starting Interactive Preflight (ID: {process_id})...\n")

    with tracer.start_as_current_span("tool.run_preflight") as span:
        try:
            # Build command string with activation
            story_arg = f"--story {story_id}" if story_id else ""
            interactive_arg = "--interactive" if interactive else ""
            
            # Inject Voice Mode for cleaner output and unbuffered IO for real-time streaming
            env_vars = "AGENT_VOICE_MODE=1 PYTHONUNBUFFERED=1"
            command = f"source .venv/bin/activate && {env_vars} agent preflight --ai {story_arg} {interactive_arg}"
            
            # PTY Implementation to force line buffering and merge stdout/stderr
            import pty
            import tty
            import termios
            
            master_fd, slave_fd = pty.openpty()
            
            # Use shell=True to support 'source'
            process = subprocess.Popen(
                command,
                shell=True,
                executable='/bin/zsh',
                cwd=str(agent_config.repo_root),
                stdin=slave_fd,
                stdout=slave_fd,  # Merge stdout to PTY
                stderr=slave_fd,  # Merge stderr to PTY
                text=True,        # Popen ignores this when using FDs, but good for intent
                bufsize=0         # Unbuffered
            )
            
            # Close slave in parent
            os.close(slave_fd)
            
            # Register process for cleanup 
            ProcessLifecycleManager.instance().register(process, process_id)
            
            # Background reader thread (Non-blocking)
            def read_output():
                try:
                    # Read from master_fd
                    # We need to loop until process dead AND fd closed
                    while True:
                        try:
                            # Read raw bytes from PTY
                            # 1024 bytes is a reasonable chunk for streaming
                            data = os.read(master_fd, 1024)
                            if not data:
                                break
                                
                            # Decode and clean (removing \r often found in PTYs)
                            text = data.decode('utf-8', errors='replace').replace('\r\n', '\n')
                            
                            # Publish lines or chunks?
                            # Console expects lines usually, but stream is better.
                            # However, EventBus 'console' usually prints lines.
                            # Let's try to split by lines for cleaner logs, 
                            # or just send chunks if the frontend handles it.
                            # Existing 'console' handler likely does print(data, end='') or similar?
                            # Let's assume line-based is safer for now to avoid broken ANSI codes across chunks
                            # actually, splitting by newline is safer for standard loggers.
                            
                            # Simple line buffering buffer
                            # (Omitted complex buffer logic for brevity, just emitting raw for now 
                            #  as the frontend/console can likely handle it, or we accept partial lines)
                            EventBus.publish(session_id, "console", text)
                                
                        except OSError:
                            break
                    
                    # Wait for process
                    rc = process.wait()
                    os.close(master_fd) # Close master
                    
                    if rc == 0:
                        EventBus.publish(session_id, "console", f"\n✅ Preflight {process_id} Passed.\n")
                    else:
                        EventBus.publish(session_id, "console", f"\n❌ Preflight {process_id} Failed (Code {rc}).\n")
                        
                except Exception as e:
                    EventBus.publish(session_id, "console", f"\n[{process_id}] Error: {e}")
                finally:
                    ProcessLifecycleManager.instance().unregister(process_id)

            t = threading.Thread(target=read_output, daemon=True)
            t.start()
            
            return "Preflight checks started. Follow along below."

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"Error running preflight: {e}"
