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

# Try to import internal services. 
# We assume the agent package is installed in the environment.
try:
    from agent.core.config import config as agent_config
    from agent.core.ai import ai_service
except ImportError:
    pass

@tool
def validate_and_fix_story(story_id: str, config: RunnableConfig = None) -> str:
    """
    Validate a story's schema. If validation fails (missing sections), 
    it attempts to use AI to generate the missing sections and fix the file.
    Args:
        story_id: The ID of the story (e.g. 'WEB-001').
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    EventBus.publish(session_id, "console", f"> Validating story {story_id}...\n")
    
    # 1. Run Validation
    def run_val():
        return subprocess.run(
            f"source .venv/bin/activate && agent validate-story {story_id}",
            shell=True,
            executable='/bin/zsh',
            capture_output=True,
            text=True
        )

    result = run_val()
    
    if result.returncode == 0:
        return f"Story {story_id} is valid."

    # 2. Analyze failure
    output = result.stdout + result.stderr
    EventBus.publish(session_id, "console", f"[yellow]Validation failed. Attempting auto-fix...[/yellow]\n")
    
    # Check for missing sections msg from check.py
    # "Missing sections: Problem Statement, User Story"
    match = re.search(r"Missing sections: (.*)", output)
    if not match:
        return f"Validation failed but could not identify missing sections to fix.\nOutput: {output}"
        
    missing_sections = [s.strip() for s in match.group(1).split(",")]
    
    # 3. Find file
    story_file = None
    for file_path in agent_config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            story_file = file_path
            break
            
    if not story_file:
        return f"Could not find story file for {story_id}."
        
    content = story_file.read_text()
    
    # 4. Generate Content
    EventBus.publish(session_id, "console", f"[dim]Generating: {', '.join(missing_sections)}[/dim]\n")
    
    prompt = f"""
    You are an expert technical product manager.
    The following user story is missing required governance sections: {', '.join(missing_sections)}.
    
    Current Content:
    {content}
    
    Task:
    Generate the content for the missing sections relative to the existing context.
    Return ONLY the markdown for the missing sections, starting with their headers (e.g. ## Problem Statement).
    Do not repeat existing sections.
    """
    
    try:
        # Initialize AI if needed (assumes env vars set or previously set)
        # We rely on default provider configuration
        generated = ai_service.complete("You are a helpful assistant.", prompt)
        
        if not generated:
            return "AI returned empty content. Fix failed."
            
        # 5. Append/Merge
        # Simple append for now. A smarter merge would find logical order, 
        # but check.py only checks for existence.
        new_content = content + "\n\n" + generated
        story_file.write_text(new_content)
        
        EventBus.publish(session_id, "console", f"[green]Updated file. Re-validating...[/green]\n")
        
        # 6. Re-Verify
        result_retry = run_val()
        if result_retry.returncode == 0:
             return f"Fixed story {story_id}. Validation now passes."
        else:
             return f"Attempted fix, but validation still failed.\nOutput: {result_retry.stdout}"

    except Exception as e:
        return f"Error during auto-fix: {e}"
