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

from typing import Any, Dict


def generate_impact_prompt(diff: str, story: str, metadata: Dict[str, Any] = None) -> str:
    """
    Generate a prompt for the AI to analyze the impact of changes.
    
    Args:
        diff: The git diff of the changes (should be scrubbed of PII).
        story: The content of the story (optional).
        metadata: Additional metadata about the changes.
        
    Returns:
        A string prompt for the AI.
    """
    prompt = f"""
You are an expert Senior Software Architect and Release Engineer.
Your task is to analyze the following code changes and determine their impact on the system.

CONTEXT:
Story Content:
{story}

Code Changes (Diff):
{diff}

INSTRUCTIONS:
1. Analyze the changes for:
    - Breaking changes (API signatures, database schemas, behavior changes).
    - Affected components (files, modules, services).
    - Risks (security, performance, compatibility).
    - Dependencies (new libraries, version changes).
2. Start your response with a clear summary.
3. Provide a structured "Impact Analysis Summary" that can be inserted into the Story document.
   The structure MUST be:
   
   ## Impact Analysis Summary
   Components touched: [List of files/components]
   Workflows affected: [List of workflows]
   Risks identified: [List of risks]
   Breaking Changes: [Yes/No - Detail if Yes]

4. Be concise but thorough.

RESPONSE FORMAT:
Markdown.
"""
    return prompt.strip()


def generate_fix_options_prompt(failure_type: str, context: Dict[str, Any], feedback: str = None) -> str:
    """
    Generate a prompt for the AI to propose fixes.
    Args:
        feedback: Optional user feedback to guide option generation (e.g. "Make it more detailed").
    """
    if failure_type == "story_schema":
        story_content = context.get("content", "")
        missing = context.get("missing_sections", [])
        
        base_prompt = f"""
You are an expert Agile Coach and Technical Writer.
A User Story is missing required sections: {missing}.

STORY CONTENT:
{story_content}

TASK:
Generate 2-3 distinct options to fix this schema violation.
"""

        if feedback:
            base_prompt += f"\nUSER FEEDBACK ON PREVIOUS OPTIONS:\n'{feedback}'\n\nADJUST GENERATION ACCORDINGLY.\n"

        base_prompt += """
OPTIONS TO GENERATE:
1. Minimal Placeholder: Just add the missing headers with empty placeholders.
2. AI Generated: Try to infer the content based on the Problem Statement/User Story provided.

OUTPUT FORMAT:
Return a JSON list of objects. Do NOT wrap in markdown code blocks.
[
  {
    "title": "Minimal Fix",
    "description": "Adds missing headers with empty placeholders.",
    "patched_content": "...full file content..."
  },
  {
    "title": "AI Generated Content",
    "description": "Attempts to write the missing sections.",
    "patched_content": "...full file content..."
  }
]
"""
        return base_prompt
    return "Invalid failure type."
