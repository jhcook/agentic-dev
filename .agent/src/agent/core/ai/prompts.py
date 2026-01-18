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
