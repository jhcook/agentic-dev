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

import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError

console = Console()
app = typer.Typer(help="Manage the Agent Management Console.")

PID_FILE = Path(".agent/run/admin.json")
LOG_DIR = Path(".agent/logs")

class ProcessManager:
    def __init__(self):
        self.pid_file = PID_FILE
        self.log_dir = LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.stopping = False

    def _is_port_in_use(self, port: int) -> bool:
        """Checks if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def _get_pids(self) -> Optional[dict]:
        """Reads PIDs from the PID file."""
        if not self.pid_file.exists():
            return None
        try:
            return json.loads(self.pid_file.read_text())
        except json.JSONDecodeError:
            return None

    def _write_pids(self, backend_pid: int, frontend_pid: int):
        """Writes PIDs to the PID file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(json.dumps({
            "backend_pid": backend_pid,
            "frontend_pid": frontend_pid
        }))

    def _clean_pid_file(self):
        """Removes the PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def start(self, follow: bool = False):
        """Starts the backend and frontend processes."""
        # --- Credential Check ---
        try:
            validate_credentials()
        except MissingCredentialsError as e:
            console.print(e)
            sys.exit(1)
        # ------------------------

        current_pids = self._get_pids()
        if current_pids:
            # Check if processes are actually running
            if self._check_running(current_pids):
                console.print("[bold yellow]Agent Console is already running.[/bold yellow]")
                self.status()
                if follow:
                    self.follow_logs(cleanup=True)
                return
            else:
                console.print("[dim]Found stale PID file. Cleaning up...[/dim]")
                self._clean_pid_file()

        # Check ports
        if self._is_port_in_use(8000) or self._is_port_in_use(8080):
            console.print("[bold red]Error: Port 8000 or 8080 is already in use.[/bold red]")
            console.print("Please stop existing processes or free up the ports manually.")
            raise typer.Exit(1)

        # Log files
        backend_log = (self.log_dir / "admin_backend.log").open("w")
        frontend_log = (self.log_dir / "admin_frontend.log").open("w")

        # Determine python executable
        # Prefer local .venv if it exists
        if os.path.exists(".venv/bin/python"):
             python_exec = os.path.abspath(".venv/bin/python")
        else:
             python_exec = sys.executable

        # 1. Start Backend (Uvicorn)
        backend_cmd = [
            python_exec, "-m", "uvicorn",
            "backend.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"
        ]
        console.print("[bold green]Starting Backend...[/bold green]")
        
        # We need to run from project root so .agent/src is in path logic usually handles this
        # But let's be safe and set PYTHONPATH if needed, or rely on cwd
        backend_proc = subprocess.Popen(
            backend_cmd,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            cwd=".agent/src",
            start_new_session=True # Detach
        )

        # 2. Start Frontend (Vite)
        if not os.path.exists(".agent/src/web"):
             console.print("[bold red]Error: '.agent/src/web' directory not found.[/bold red]")
             backend_proc.terminate()
             raise typer.Exit(1)

        frontend_cmd = ["npm", "run", "dev"]
        console.print("[bold blue]Starting Frontend...[/bold blue]")
        
        # Vite keeps port 8080 logic in config, but we can't easily force it via CLI args without changes
        # relying on vite.config.ts port setting we made earlier.
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
            cwd=".agent/src/web",
            start_new_session=True # Detach
        )

        self._write_pids(backend_proc.pid, frontend_proc.pid)

        console.print("[bold]Agent Console started![/bold]")
        console.print("  Backend: http://127.0.0.1:8000")
        console.print("  Frontend: http://127.0.0.1:8080")
        console.print(f"  Logs: {self.log_dir}/admin_*.log")

        if follow:
            self.follow_logs(cleanup=True)

    def stop(self):
        """Stops the running processes."""
        if self.stopping:
            return
        self.stopping = True

        # Ignore Ctrl+C (SIGINT) during shutdown to prevent interruption/tracebacks
        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        try:
            pids = self._get_pids()
            if not pids:
                console.print("[yellow]Agent Console is not running (no PID file found).[/yellow]")
                return

            console.print("[bold yellow]Stopping services...[/bold yellow]")
            
            import time

            for name, pid in pids.items():
                try:
                    # 1. Try Graceful Shutdown (SIGTERM)
                    if sys.platform != "win32":
                        os.killpg(pid, signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                    
                    console.print(f"  Sent SIGTERM to {name} ({pid})...")
                    
                    # 2. Wait up to 5s for exit (50 * 0.1s)
                    for _ in range(50):
                        try:
                            time.sleep(0.1)
                        except KeyboardInterrupt:
                            pass # Force wait
                            
                        try:
                            os.kill(pid, 0) # Check if still exists
                        except ProcessLookupError:
                            break # Process is gone
                        except OSError as e:
                            if e.errno == 1: # EPERM: Process exists but zombie/no perm
                                # If it's a zombie, we can't kill it, so waiting is futile.
                                # Treat as "gone" for our purposes or break to force kill attempt (which might fail too)
                                # Better to break and try force kill, catching EPERM there.
                                break 
                            pass # Other errors, keep waiting?
                    else:
                        # 3. Force Kill (SIGKILL)
                        console.print(f"  [bold red]Process {name} did not exit. Sending SIGKILL...[/bold red]")
                        if sys.platform != "win32":
                            try:
                                os.killpg(pid, signal.SIGKILL)
                            except (ProcessLookupError, OSError):
                                pass
                        else:
                            try:
                                os.kill(pid, signal.SIGKILL)    
                            except (ProcessLookupError, OSError):
                                pass
                            
                except ProcessLookupError:
                    console.print(f"  Process {name} ({pid}) already gone.")
                except Exception as e:
                    console.print(f"  Error stopping {name}: {e}")

            self._clean_pid_file()
            console.print("[bold green]Services stopped.[/bold green]")
        finally:
            # Restore signal handler (though usually we exit right after)
            signal.signal(signal.SIGINT, original_sigint)
            self.stopping = False

    def status(self):
        """Checks the status of the processes."""
        pids = self._get_pids()
        if not pids:
            console.print("[dim]Agent Console is stopped.[/dim]")
            return

        running = self._check_running(pids)
        if running:
            console.print("[bold green]Agent Console is running.[/bold green]")
            console.print(f"  Backend PID: {pids['backend_pid']}")
            console.print(f"  Frontend PID: {pids['frontend_pid']}")
        else:
            console.print("[bold red]Stale PID file found (processes not running).[/bold red]")
            # Optional: clean up?

    def _check_running(self, pids: dict) -> bool:
        """Checks if PIDs verify as running processes."""
        # Simple check: can we send signal 0?
        try:
            os.kill(pids["backend_pid"], 0)
            os.kill(pids["frontend_pid"], 0)
            return True
        except ProcessLookupError:
            return False
        except OSError as e:
            if e.errno == 1: # EPERM means it exists
                return True
            return False
        except Exception:
            return False # Conservative

    def follow_logs(self, cleanup: bool = False):
        """Streams logs from files to stdout.
        
        Args:
            cleanup: If True, stops processes when logging is interrupted.
        """
        console.print("[dim]Streaming logs (Ctrl+C to stop streaming, processes continue)...[/dim]")
        
        # Simple tail implementation using `tail -f`
        # Using subprocess for efficiency
        log_files = [
            str(self.log_dir / "admin_backend.log"),
            str(self.log_dir / "admin_frontend.log")
        ]
        
        try:
            # tail -f file1 file2
            subprocess.run(["tail", "-f"] + log_files)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped following logs.[/dim]")
            if cleanup:
                console.print("[yellow]Interrupted. Stopping services...[/yellow]")
                self.stop()


manager = ProcessManager()

@app.command()
def start(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output in console")
):
    """
    Start the Agent Management Console (Detached by default).
    """
    manager.start(follow=follow)
    


@app.command()
def stop():
    """
    Stop the Agent Management Console.
    """
    manager.stop()

@app.command()
def status():
    """
    Check the status of the Agent Management Console.
    """
    manager.status()