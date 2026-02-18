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
IMPORTANT: You MUST escape all double quotes and newlines within the JSON strings to ensure it is parseable.
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
    elif failure_type == "governance_rejection":
        findings = context.get("findings", [])
        content = context.get("content", "")
        
        base_prompt = f"""
You are an expert Senior Software Engineer and Security Lead.
The Governance Council has BLOCKED a preflight check. You need to propose fixes.

FINDINGS / BLOCKING ISSUES:
{chr(10).join(findings)}

FILE CONTENT:
{content}

TASK:
Generate 2 distinct options to resolve these findings by modifying the code.

OPTIONS TO GENERATE:
1. Conservative Fix: Minimal changes to address the findings (e.g. adding logs, adding checks).
2. Refactor Fix: A cleaner, more robust implementation if applicable.

CRITICAL RESPONSE GUIDELINES:
- You are a JSON generator. You do NOT speak.
- Output ONLY valid JSON array.
- Do NOT use markdown code blocks (```json).
- IMPORTANT: Escape all double quotes (\") and newlines (\\n) inside string values.
- Do NOT provide an introduction or conclusion.
- If you cannot generate a fix, return an empty list [].

OUTPUT FORMAT:
[
  {{
    "title": "Conservative Fix",
    "description": "Minimal changes to address findings.",
    "patched_content": "...FULL file content with fix applied..."
  }},
  {{
    "title": "Refactor Fix",
    "description": "Robust implementation addressing findings.",
    "patched_content": "...FULL file content with fix applied..."
  }}
]
"""
        return base_prompt

    elif failure_type == "test_failure":
        test_output = context.get("test_output", "")
        content = context.get("content", "")
        test_file = context.get("test_file", "unknown_test.py")
        
        # Manually escape significant characters if not using json.dumps for the whole prompt
        # But better to just let the LLM handle raw text if wrapped.
        # The QA finding specifically asks for escaping in the JSON strings of the *prompt generation*.
        # We will use triple quotes which usually handles newlines, but for logic safety:
        # We prefer to keep it readable, but if QA demands escaping, we'll use json.dumps for the content block.
        import json
        escaped_output = json.dumps(test_output)
        
        base_prompt = f"""
You are an expert QA Engineer and Python Developer.
A unit test has failed. Your task is to propose fixes for the TEST FILE to resolve the failure.
Note: We are primarily fixing the test code itself (e.g. updating assertions, fixing logic), but if the fix is obvious in the prompt, you might suggest it.
However, you only have write access to the test file content provided below.

TEST FAILURE OUTPUT:
{escaped_output}

TEST FILE CONTENT ({test_file}):
{content}

TASK:
Generate 2-3 distinct options to resolve the test failure by modifying the TEST FILE.

OPTIONS TO GENERATE:
1. Fix Syntax: Correct syntax errors (e.g. indentation, missing parens, invalid syntax).
2. Fix Assertion: Update expectations to match reality if the code behavior is correct but test is outdated.
3. Fix Logic: Correct bugs in the test setup/teardown or logic.
4. Skip/Ignore: Mark test as skipped (e.g. @pytest.mark.skip) if it's a known issue to be fixed later (use sparingly).

CRITICAL RESPONSE GUIDELINES:
- You are a JSON generator. You do NOT speak.
- Output ONLY valid JSON array.
- Do NOT use markdown code blocks (```json).
- IMPORTANT: Escape all double quotes (\") and newlines (\\n) inside string values.
- Changes must be valid Python code.

OUTPUT FORMAT:
[
  {{
    "title": "Fix Assertion",
    "description": "Updates the expected value.",
    "patched_content": "...FULL file content with fix applied..."
  }},
  {{
    "title": "Skip Test",
    "description": "Temporarily skips the failing test.",
    "patched_content": "...FULL file content with fix applied..."
  }}
]
"""
        return base_prompt

    return "Invalid failure type."


def generate_test_prompt(
    data: Dict[str, Any], jid: str, source_context: str
) -> tuple[str, str]:
    """Generate a (system_prompt, user_prompt) tuple for AI test generation.

    Args:
        data: Parsed journey YAML data.
        jid: Journey ID (e.g. JRN-053).
        source_context: Scrubbed source code context from implementation.files.

    Returns:
        Tuple of (system_prompt, user_prompt) for AIService.complete().
    """
    steps = data.get("steps", [])
    steps_text = "\n".join(
        f"  {i}. {s.get('action', 'unnamed')}"
        + (
            ("\n     Assertions: " + ", ".join(s.get("assertions", [])))
            if s.get("assertions")
            else ""
        )
        for i, s in enumerate(steps, 1)
        if isinstance(s, dict)
    )
    slug = jid.lower().replace("-", "_")

    system_prompt = """You are an expert Python test engineer.
Write complete, executable pytest test modules.
Output ONLY valid Python code — no markdown fences, no explanations.
All generated code must pass `ast.parse()` without errors."""

    user_prompt = f"""Write a pytest test module for user journey {jid}.

JOURNEY STEPS:
{steps_text}

SOURCE CODE CONTEXT:
{source_context if source_context else "No source files available."}

REQUIREMENTS:
- Use pytest framework only (no unittest, no selenium).
- Include `import pytest` at the top.
- Add `@pytest.mark.journey("{jid}")` decorator on each test function.
- Name test functions as `test_{slug}_step_N` (one per journey step).
- Write real assertions based on the step assertions (not `pytest.skip`).
- Mock external dependencies with `unittest.mock` as needed.
- Include descriptive docstrings referencing the step action.
- Output ONLY valid Python code, no markdown fences.
"""
    return system_prompt, user_prompt

