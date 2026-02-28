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


import subprocess
import atexit
import logging
import threading

logger = logging.getLogger(__name__)

class ProcessLifecycleManager:
    """
    Singleton manager to track subprocesses spawned by the Agent.
    Ensures that child processes are killed when the main process exits.
    """
    _instance = None
    
    def __init__(self):
        if ProcessLifecycleManager._instance is not None:
             raise Exception("This class is a singleton!")
        
        # Store processes mapped by ID for retrieval
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        
        # Register cleanup hooks
        atexit.register(self.kill_all)
        
        # Optional: Hook signals if not already handled by framework (FastAPI/Uvicorn usually handle this)
        # We'll just rely on atexit for now, which covers normal exits.
        # For SIGTERM (e.g. docker stop), we might need explicit handling 
        # but messing with signals in a library can conflict with the app server.
        # We'll expose a methods for the app to call if needed.
        
        logger.info("ProcessLifecycleManager initialized.")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with threading.Lock():
                if cls._instance is None:
                    cls._instance = ProcessLifecycleManager()
        return cls._instance

    def register(self, process: subprocess.Popen, process_id: str = None):
        """
        Register a process to be tracked.
        Args:
            process: The Popen object
            process_id: Unique ID for retrieval. If None, uses pid.
        """
        pid_key = process_id or str(process.pid)
        with self._lock:
            self._processes[pid_key] = process
        logger.debug(f"Registered process {process.pid} as {pid_key}")
        return pid_key

    def unregister(self, process_id_or_obj):
        """Unregister a process by ID or object."""
        with self._lock:
            if isinstance(process_id_or_obj, subprocess.Popen):
                # Reverse lookup (slow but rare)
                keys_to_remove = [k for k, v in self._processes.items() if v == process_id_or_obj]
                for k in keys_to_remove:
                    del self._processes[k]
            elif isinstance(process_id_or_obj, str) and process_id_or_obj in self._processes:
                del self._processes[process_id_or_obj]
        
    def get(self, process_id: str) -> subprocess.Popen:
        """Retrieve a process by ID."""
        with self._lock:
            return self._processes.get(process_id)

    def kill_all(self):
        """Force kill all tracked processes."""
        with self._lock:
            if not self._processes:
                return
            
            logger.info(f"Cleaning up {len(self._processes)} orphaned processes...")
            # Create a list of processes to iterate
            processes_to_kill = list(self._processes.values())
            for p in processes_to_kill:
                try:
                    if p.poll() is None: # Still running
                        logger.warning(f"Killing orphaned process {p.pid}")
                        p.terminate()
                        # Give it a tiny bit to die gracefully, then kill
                        try:
                            p.wait(timeout=0.1)
                        except subprocess.TimeoutExpired:
                            p.kill()
                except Exception as e:
                    logger.error(f"Failed to kill process {p.pid}: {e}")
            self._processes.clear()
