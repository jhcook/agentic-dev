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
from backend.voice.process_manager import ProcessLifecycleManager
from backend.voice.events import EventBus
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tool
def start_interactive_shell(command: str, session_id: str = None, config: RunnableConfig = None) -> str:
    """
    Start a long-running interactive shell command (e.g., 'npm init', 'python3').
    Returns a Process ID that can be used with send_shell_input.
    Output will be streamed to the console.
    """
    if not session_id and config:
        session_id = config.get("configurable", {}).get("thread_id", "unknown")
        
    process_id = f"shell-{int(time.time())}"
    
    try:
        # Use shell=True and Setsid?
        # Standard Popen with pipes
        process = subprocess.Popen(
            command,
            shell=True,
            executable='/bin/zsh',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1, # Line buffered
            cwd=os.getcwd()
        )
        
        # Register with ID
        ProcessLifecycleManager.instance().register(process, process_id)
        
        # Start background reader thread
        def read_output():
            try:
                for line in iter(process.stdout.readline, ''):
                    EventBus.publish(session_id, "console", f"[{process_id}] {line}")
                process.stdout.close()
                ProcessLifecycleManager.instance().unregister(process_id)
                EventBus.publish(session_id, "console", f"\n[{process_id}] Process exited with code {process.wait()}.")
            except Exception as e:
                EventBus.publish(session_id, "console", f"\n[{process_id}] Reader Error: {e}")

        t = threading.Thread(target=read_output, daemon=True)
        t.start()
        
        return f"Started interactive process '{command}'. ID: {process_id}. Output will stream to console."
        
    except Exception as e:
        return f"Failed to start process: {e}"

@tool
def send_shell_input(process_id: str, input_text: str) -> str:
    """
    Send text input to a running interactive process.
    Args:
        process_id: The ID returned by start_interactive_shell.
        input_text: The text to send (newline will be appended automatically).
    """
    process = ProcessLifecycleManager.instance().get(process_id)
    if not process:
        return f"Error: Process {process_id} not found or not running."
    
    if process.poll() is not None:
        return f"Error: Process {process_id} has already exited."
        
    try:
        # Write to stdin
        if input_text and not input_text.endswith('\n'):
            input_text += '\n'
            
        process.stdin.write(input_text)
        process.stdin.flush()
        return f"Sent input to {process_id}."
    except Exception as e:
        return f"Error sending input: {e}"
