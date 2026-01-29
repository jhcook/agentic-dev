
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
from pathlib import Path
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
    Interactively fix a story schema using AI.
    
    modes:
    1. ANALYZE (Default): If apply_idx is None, scans the story for errors and returns a list of suggested fixes.
       Provide 'instructions' to guide the AI generation (e.g. "make it more detailed").
       
    2. APPLY: If apply_idx is provided (1-based index), applies that fix option immediately.
    
    Args:
        story_id: The ID of the story (e.g. 'WEB-001').
        apply_idx: Optional 1-based index of the fix option to apply.
        instructions: Optional instructions for the AI ("Try again but...").
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
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
    # We run the actual check logic or just assume failures based on request.
    # InteractiveFixer.analyze_failure does re-read the file.
    
    # We must first "Analyze" to get options.
    # NOTE: Since tools are stateless, we must regenerate options or cache them.
    # For now, to keep it simple, we regenerate.
    # Ideally, we should pass the same 'instructions' if we want the same set, 
    # but the User flow is Analyze -> Speak -> User Picks -> Apply.
    # If the user picks '1', we need to regenerate option 1 to apply it.
    # This assumes determinism or that we accept slight variations.
    # A true stateful solution would cache the latest options in the session.
    # Given the constraints, regenerating with high temperature=0 logic is best, specific to the fixer prompts.
    
    # Ideally checking validation first:
    def check_val():
        return subprocess.run(
            f"source .venv/bin/activate && agent validate-story {story_id}",
            shell=True, executable='/bin/zsh', capture_output=True, text=True
        )

    res = check_val()
    if res.returncode == 0 and not instructions:
        # If valid and no instructions to force changes, we are done.
        return f"Story {story_id} is already valid."
    
    output = res.stdout + res.stderr
    missing_match = re.search(r"Missing sections: (.*)", output)
    missing = [s.strip() for s in missing_match.group(1).split(",")] if missing_match else []
    
    context = {
        "story_id": story_id,
        "missing_sections": missing,
        "file_path": str(story_file)
    }
    
    # GENERATE OPTIONS
    EventBus.publish(session_id, "console", f"[dim]Analyzing failure/options...[/dim]\n")
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
                    r = check_val()
                    return r.returncode == 0
                
                if fixer.verify_fix(validation_callback, confirm=False):
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
