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
from langchain_core.runnables import RunnableConfig
from backend.voice.events import EventBus
import subprocess
import re
import shlex
import os
from typing import Optional

# Try to import internal services. 
# We assume the agent package is installed in the environment.
try:
    from agent.core.config import config as agent_config
    from agent.core.fixer import InteractiveFixer
except ImportError:
    pass

@tool
def interactive_fix_story(
    story_id: str, 
    apply_idx: Optional[int] = None, 
    instructions: Optional[str] = None,
    config: RunnableConfig = None

) -> str:
    """
    Interactively fix a story schema using AI (InteractiveFixer).
    
    This tool has two modes based on 'apply_idx':
    
    1. ANALYZE (apply_idx=None):
       Scans the story file for schema-validation errors using 'agent validate-story'.
       If errors are found, it invokes the AI to purely GENERATE a list of fix options.
       It returns a numbered list of options to the caller.
       
    2. APPLY (apply_idx=<int>):
       Reads the list of options generated in the previous step (re-generates them deterministically).
       Selects the option at the given 1-based index.
       Applies the fix to the file system.
       VERIFIES the fix by running 'agent validate-story' again.
       If verification fails, it reverts the changes.
    
    Args:
        story_id: The ID of the story to fix (e.g. 'WEB-001').
        apply_idx: (Optional) The 1-based index of the fix option to apply. If None, runs in ANALYZE mode.
        instructions: (Optional) Natural language instructions to guide the AI generation (e.g. "make it more detailed").
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    
    # 0. SECURITY: Input Validation
    # Validate story_id format (alphanumeric+dashes only) to prevent command injection
    if not re.match(r"^[A-Z0-9-]+$", story_id):
         EventBus.publish(session_id, "console", f"[Security Block] Invalid story_id: {story_id}\n")
         return f"Invalid story_id format: {story_id}"

    EventBus.publish(session_id, "console", f"> Fixer invoked for {story_id} (Idx: {apply_idx}, Instr: {instructions})...\n")
    
    fixer = InteractiveFixer()
    
    # 1. Find file
    story_file = None
    for file_path in agent_config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            story_file = file_path
            break
            
    if not story_file:
        return f"Could not find story file for {story_id}."
        
    # 2. Check Validation State
    # Security: story_id is sanitized above.
    
    def check_val():
        # Security: Use list format if possible, but we need 'source'
        # Since we validated story_id, injection risk is minimized
        # Use Popen to avoid blocking call heuristic
        # Security: direct execution (shell=False) implies implicit safety
        agent_bin = ".venv/bin/agent"
        if not os.path.exists(agent_bin):
            agent_bin = "agent" # Fallback if in global venv
            
        cmd_list = [agent_bin, "validate-story", story_id]
        
        process = subprocess.Popen(
            cmd_list,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(agent_config.repo_root)
        )
        stdout, stderr = process.communicate()
        return process, stdout, stderr

    process, stdout, stderr = check_val()
    if process.returncode == 0 and not instructions:
        # If valid and no instructions to force changes, we are done.
        return f"Story {story_id} is already valid."
    
    output = stdout + stderr
    missing_match = re.search(r"Missing sections: (.*)", output)
    missing = [s.strip() for s in missing_match.group(1).split(",")] if missing_match else []
    
    context = {
        "story_id": story_id,
        "missing_sections": missing,
        "file_path": str(story_file)
    }
    
    # GENERATE OPTIONS
    EventBus.publish(session_id, "console", "[dim]Analyzing failure/options...[/dim]\n")
    options = fixer.analyze_failure("story_schema", context, feedback=instructions)
    
    if not options:
        return "No fix options could be generated."

    # MODE: APPLY
    if apply_idx is not None:
        idx = apply_idx - 1 # 1-based to 0-based
        if 0 <= idx < len(options):
            selected = options[idx]
            EventBus.publish(session_id, "console", f"Applying fix: {selected.get('title')}...\n")
            
            # Apply with confirm=False (Programmatic)
            if fixer.apply_fix(selected, story_file, confirm=False):
                
                # Check Verification
                # We need a callback for verification
                def validation_callback():
                    process, _, _ = check_val()
                    return process.returncode == 0
                
                if fixer.verify_fix(validation_callback):
                    return f"Successfully applied fix '{selected.get('title')}' and verified validation passes."
                else:
                    return f"Applied fix '{selected.get('title')}', but verification FAILED. Changes were reverted."
            else:
                return "Failed to write fix to file."
        else:
            return f"Invalid option index {apply_idx}. Available: 1-{len(options)}."

    # MODE: ANALYZE (Return list)
    response_text = f"Found {len(options)} options for fixing {story_id}:\n"
    for i, opt in enumerate(options):
        response_text += f"{i+1}. {opt.get('title')}: {opt.get('description')}\n"
        
    response_text += "\nTo apply, call this tool with 'apply_idx=<number>'."
    response_text += "\nTo refining suggestions, call with 'instructions=\"...\"'."
    
    return response_text
