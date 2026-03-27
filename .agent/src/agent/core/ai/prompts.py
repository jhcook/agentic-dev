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

from typing import Any, Dict, List, Optional


def generate_skeleton_prompt(story_content: str, metadata: Dict[str, Any] = None) -> str:
    """
    Generate a Phase 1 prompt for creating a runbook skeleton.

    Args:
        story_content: The full content of the User Story.
        metadata: Additional metadata about the environment or story.

    Returns:
        A system prompt for the AI.
    """
    prompt = f"""
You are the Lead Architect in the AI Governance Panel.
Your task is to generate a high-level Implementation Skeleton for the following User Story.

STORY CONTENT:
{story_content}

METADATA:
{metadata or "None"}

TASK:
Identify all necessary sections for a comprehensive implementation runbook.
For each section, provide a title, a brief description of what it should cover,
an estimated token weight, AND a list of files that section will touch.

MANDATORY SECTIONS (always include these, plus any story-specific ones):
- Architecture & Design Review
- Implementation (one or more sections covering code changes)
- Security & Input Sanitization (if applicable)
- Observability & Audit Logging
- Verification & Test Suite
- Deployment & Rollback Strategy

CONDITIONAL SECTIONS (include when the story's Acceptance Criteria warrant it):
- Documentation Updates — if the story introduces new commands, CLI flags, or user-facing behavioral changes, include a section that creates or updates docs in `.agent/docs/`

CRITICAL FILE ASSIGNMENT RULE:
Each file path MUST appear in exactly ONE section's "files" list.
If multiple sections need to modify the same file, consolidate ALL changes for
that file into a SINGLE section. This prevents cascading search/replace conflicts
where later sections search for text that earlier sections already changed.

OUTPUT FORMAT:
Return ONLY a JSON object with this structure (no markdown fences, no prose):
{{
  "title": "Implementation Runbook for STORY-ID",
  "sections": [
    {{
      "title": "Section Title",
      "description": "Short description of what to implement/review here.",
      "files": [".agent/src/path/to/file.py"],
      "estimated_tokens": 500
    }}
  ]
}}

CRITICAL: Do NOT include credentials, PII, or secrets. Use placeholders if necessary.
"""
    return prompt.strip()


def _build_modify_targets_block(modify_file_contents: Optional[Dict[str, str]]) -> str:
    """Build a prompt section with actual file contents for MODIFY targets.

    Injects the exact on-disk content of files the AI may generate <<<SEARCH
    blocks for, eliminating hallucination.

    Args:
        modify_file_contents: Mapping of repo-relative paths to file content.

    Returns:
        Formatted prompt section, or empty string if no contents provided.
    """
    if not modify_file_contents:
        return ""

    entries: List[str] = []

    for path, content in modify_file_contents.items():
        # Infer language for syntax highlighting
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        lang = {"py": "python", "yaml": "yaml", "yml": "yaml",
                "json": "json", "md": "markdown", "toml": "toml"}.get(ext, "")
        entries.append(f"\n### {path}\n```{lang}\n{content}\n```")

    return (
        "\n\nMODIFY TARGET FILES — EXACT ON-DISK CONTENT "
        "(copy lines VERBATIM for <<<SEARCH blocks):\n"
        + "\n".join(entries)
    )


def generate_block_prompt(
    section_title: str,
    section_desc: str,
    skeleton_json: str,
    story_content: str,
    context_summary: str,
    prior_changes: Optional[Dict[str, str]] = None,
    modify_file_contents: Optional[Dict[str, str]] = None,
    existing_files: Optional[List[str]] = None,
) -> str:
    """
    Generate a Phase 2 prompt for creating a detailed implementation block.

    Args:
        section_title: The title of the section to generate.
        section_desc: The description of the section.
        skeleton_json: The full skeleton JSON for context.
        story_content: The original story content.
        context_summary: Relevant codebase context (targeted introspection).
        prior_changes: Dict mapping file paths to a summary of changes
            already applied by earlier sections.
        modify_file_contents: Dict mapping file paths to their actual on-disk
            content. When provided, injected verbatim so the AI can write
            exact <<<SEARCH blocks without hallucinating.

    Returns:
        A system prompt for the AI.
    """
    # Build deduplication instruction if prior sections touched files
    dedup_block = ""
    if prior_changes:
        entries = []
        for path, summary in prior_changes.items():
            entries.append(f"  - `{path}`: {summary}")
        change_list = "\n".join(entries)
        forbidden_list = ", ".join(f"`{p}`" for p in prior_changes)
        dedup_block = f"""
FORBIDDEN FILES — these were already handled by earlier sections.
You MUST NOT emit any [NEW] or [MODIFY] block for these files:
{forbidden_list}

Prior changes detail:
{change_list}

If you generate a [NEW] or [MODIFY] block for ANY file listed above, the runbook
will fail validation and be rejected. Skip those files entirely.
"""

    # Build existing-files constraint to prevent [NEW] on existing files
    existing_block = ""
    if existing_files:
        existing_list = ", ".join(f"`{p}`" for p in existing_files)
        existing_block = f"""
EXISTING FILES ON DISK — these files ALREADY EXIST and MUST use [MODIFY], NOT [NEW]:
{existing_list}

Using [NEW] for any of these files is an ERROR. If you need to change them, use
[MODIFY] with <<<SEARCH / === / >>> blocks based on the file content provided above.
"""

    prompt = f"""
You are the Implementation Specialist in the AI Governance Panel.
Your task is to generate a DETAILED implementation block for a specific section of a runbook.

TARGET SECTION:
Title: {section_title}
Objective: {section_desc}

FULL RUNBOOK SKELETON (FOR COHERENCE):
{skeleton_json}

STORY CONTEXT:
{story_content}

TARGETED FILE CONTENTS (this is the GROUND TRUTH — base all SEARCH blocks on these exact contents):
{context_summary}
{_build_modify_targets_block(modify_file_contents)}
{dedup_block}
{existing_block}
TASK:
Provide the full technical content for this section.
IMPORTANT: Do NOT start the content with a section header (## or ### title). The section header
is provided separately via the "header" field. Start content directly with an objective, description,
or the first `#### [NEW]` / `#### [MODIFY]` block. Using ## or ### headers at the top of the content
will break the document structure.

CODE CHANGE FORMAT RULES (follow these EXACTLY):
1. Use `#### [NEW] <path>` for files that DO NOT EXIST yet, followed by a fenced code block with the full file content.
2. Use `#### [MODIFY] <path>` for EXISTING files. A [MODIFY] header MUST be followed by one or more `<<<SEARCH / === / >>>` blocks ONLY.
   NEVER follow a [MODIFY] header with a fenced code block — it will be silently skipped by the parser.
3. `<<<SEARCH` blocks must contain the EXACT lines from the source file. Do NOT paraphrase, guess, or modify them.
   Base your SEARCH blocks exactly on the content provided in TARGETED FILE CONTENTS above.
4. Format for search/replace:
   ```
   <<<SEARCH
   exact existing lines
   ===
   replacement lines
   >>>
   ```
5. Use `#### [DELETE] <path>` to remove a file (requires a `rationale` line).
6. Use repository-relative paths starting with `.agent/src/` (never absolute paths).
7. Ensure all public interfaces have PEP-257 docstrings.
8. Include a troubleshooting subsection if applicable.
9. CRITICAL: Inside <<<SEARCH and >>> blocks, content is LITERAL CODE, not markdown.
   Do NOT apply markdown formatting to code identifiers. Write `__name__` not `**name**`,
   write `__init__` not `**init**`. Double underscores are Python dunder syntax, not bold.
10. DEDUPLICATION: If a file appears in PRIOR SECTIONS below, do NOT create another
    [NEW] or [MODIFY] block for that same file. Consolidate all changes to a file
    into a SINGLE section. If you need to reference prior changes, describe them in prose.
11. NEVER use [MODIFY] on a file created by [NEW] in the SAME runbook. If you are
    creating a new file, include ALL final code in a single [NEW] block. [MODIFY] must
    ONLY target pre-existing files already on disk. This prevents hallucinated SEARCH
    text that doesn't match the actual generated code.
12. TEST PLACEMENT: Test files MUST be placed in the top-level `tests/` directory,
    NEVER inside `src/`. The pattern is `<component>/tests/` mirroring the source structure.
    Example: tests for `.agent/src/agent/core/ai/` go in `.agent/tests/core/ai/`.
    Do NOT create `[NEW] .agent/src/**/tests/` paths.
13. FENCE REQUIREMENT: <<<SEARCH / === / >>> blocks MUST be wrapped inside a code fence
    (triple backticks). Without fences, the markdown parser misinterprets === as a heading
    and >>> as a blockquote, breaking the search/replace extraction.
14. HEADING LEVELS: NEVER use `### ` (h3) headings inside block content. The `### Step N:` 
    heading is placed by the pipeline automatically. Sub-sections MUST use `**Bold Text**`
    or `#### [NEW/MODIFY/DELETE]` headers only. Using `### ` headings will corrupt the
    runbook step structure by creating empty phantom steps.
15. FILE OPERATION REQUIRED: Every step MUST contain at least one `#### [NEW]`,
    `#### [MODIFY]`, or `#### [DELETE]` block. Prose-only steps fail schema validation.
    If the section is procedural (e.g. Deployment, Rollback), you MUST still emit a
    `#### [MODIFY] CHANGELOG.md` S/R block recording the change. No exceptions.

OUTPUT FORMAT:
Return ONLY a JSON object with this structure (no markdown fences, no prose):
{{
  "header": "{section_title}",
  "content": "... full markdown content (NO leading ## or ### header — start with prose or #### blocks) ..."
}}

CRITICAL: Ensure implementation blocks use repository-relative paths starting with `.agent/src/`.
CRITICAL: Do NOT include credentials, PII, or secrets. Use placeholders if necessary.
"""
    return prompt.strip()


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
   Components touched: [List of exact repository-relative file paths touched (e.g. .agent/src/agent/core/ai/prompts.py)]
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

