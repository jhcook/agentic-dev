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

import re
import logging

logger = logging.getLogger(__name__)
import json
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from agent.core.config import config

console = Console()

def get_next_id(directory: Path, prefix: str) -> str:
    """
    Finds the next available Global ID based on a prefix.
    Scans Stories, Plans, Runbooks, and local DB to ensure uniqueness per ADR-019.
    """
    # 1. Allow for 'ADR' special case (lives in its own flat dir)
    # 2. For others (INFRA, WEB, etc.), check subfolders in stories/plans/runbooks

    from agent.db.client import get_connection
    
    max_num = 0
    pattern = re.compile(f"{prefix}-(\\d+)")

    # Define paths to scan based on prefix
    paths_to_scan = []
    
    if prefix == "ADR":
        paths_to_scan.append(config.adrs_dir)
    else:
        # Scan all known artifact types that share this ID namespace
        if (config.stories_dir / prefix).exists():
            paths_to_scan.append(config.stories_dir / prefix)
        if (config.plans_dir / prefix).exists():
            paths_to_scan.append(config.plans_dir / prefix)
        if (config.runbooks_dir / prefix).exists():
            paths_to_scan.append(config.runbooks_dir / prefix)

    # A. Scan Filesystem
    for path in paths_to_scan:
        if path.exists():
            for file_path in path.glob(f"{prefix}-*.md"):
                match = pattern.search(file_path.name)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num

    # B. Scan Database (to catch things known mostly remotely or in other folders)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Look for any artifact ID starting with prefix
        # Use simple LIKE query
        query_prefix = f"{prefix}-%"
        cursor.execute("SELECT id FROM artifacts WHERE id LIKE ?", (query_prefix,))
        rows = cursor.fetchall()
        for row in rows:
            art_id = row[0]
            match = pattern.search(art_id)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        conn.close()
    except Exception as e:
        console.print(f"[yellow]⚠️  DB check failed for ID generation: {e}[/yellow]")

    next_num = max_num + 1
    return f"{prefix}-{next_num:03d}"


def sanitize_title(title: str) -> str:
    """
    Sanitizes a title for use in a filename.
    Converts to lowercase, replaces spaces with hyphens, removes non-alphanumeric chars.
    Collapses multiple hyphens and strips leading/trailing hyphens.
    """
    safe_title = title.lower().replace(" ", "-")
    safe_title = re.sub(r"[^a-z0-9-]", "", safe_title)
    safe_title = re.sub(r"-+", "-", safe_title) # Collapse hyphens
    return safe_title.strip("-")

def get_current_branch():
    try:
        return subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    except Exception:
        return ""

def infer_story_id() -> Optional[str]:
    branch = get_current_branch()
    if not branch:
        return None
        
    match = re.search(r"([A-Z]+-[0-9]+)", branch)
    if match:
        console.print(f"🛈 Inferred story ID from branch: {match.group(1)}")
        return match.group(1)
        
    console.print(f"[yellow]⚠️  Could not infer Story ID from branch '{branch}'.[/yellow]")
    
    # Fuzzy match
    found_match = None
    for file_path in config.stories_dir.rglob(f"*{branch}*"):
        if file_path.name.endswith(".md"):
             match_id = re.search(r"^([A-Z]+-[0-9]+)", file_path.name)
             if match_id:
                 found_match = match_id.group(1)
                 if typer.confirm(f"Found matching story {found_match} ({file_path.name}). Use this?"):
                     return found_match
                     
    story_input = Prompt.ask("Please enter Story ID (or 'skip' to bypass governance - NOT RECOMMENDED)")
    if story_input == "skip":
        console.print("[yellow]⚠️  Proceeding without Story ID. Governance checks will be skipped.[/yellow]")
        return None
    elif story_input:
        return story_input
        
    return None

def find_story_file(story_id: str) -> Optional[Path]:
    """
    Find a story file by its ID.

    Searches recursively in the stories directory for a file starting with the given ID.

    Args:
        story_id: The ID of the story to find (e.g., "STORY-123").

    Returns:
        Optional[Path]: The path to the story file if found, None otherwise.
    """
    if not story_id:
        return None
        
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        # Ensure it matches the ID prefix strictly to avoid partial matches if intended
        if file_path.name.startswith(story_id):
            return file_path
    return None

    return context

def load_governance_context(coding_only: bool = False) -> str:
    """
    Load governance rules from the rules directory.
    
    Args:
        coding_only: If True, filters out non-coding related rules (process/roles)
                     to save context window space.
    """
    context = "GOVERNANCE RULES:\n"
    has_rules = False
    
    # Process-related rules to skip when coding_only is True
    
    # Whitelist of critical rules for coding tasks to minimize context size
    CODING_WHITELIST = {
        "lean-code.mdc",
        "test.mdc",
        "main.mdc"
    }

    if config.rules_dir.exists():
        for rule_file in sorted(config.rules_dir.glob("*.mdc")):
            # If strictly coding, we skip anything NOT in the whitelist
            if coding_only and rule_file.name not in CODING_WHITELIST:
                continue
            
            # Legacy blacklist fallback (if we weren't using whitelist logic, which we are now replacing)
            # if coding_only and rule_file.name in PROCESS_RULES: continue
                
            has_rules = True
            context += f"\n--- RULE: {rule_file.name} ---\n"
            context += rule_file.read_text(errors="ignore")
    
    if not has_rules:
        context += "(No rules found)"
    return context

def find_runbook_file(runbook_id: str) -> Optional[Path]:
    """
    Find a runbook file by its ID.

    Searches recursively in the runbooks directory for a file starting with the given ID.

    Args:
        runbook_id: The ID of the runbook to find.

    Returns:
        Optional[Path]: The path to the runbook file if found, None otherwise.
    """
    if not runbook_id:
        return None
        
    for file_path in config.runbooks_dir.rglob(f"{runbook_id}*.md"):
        if file_path.name.startswith(runbook_id):
            return file_path
    return None

def scrub_sensitive_data(text: str) -> str:
    """
    Scrub sensitive data (PII, Secrets) from text using regex patterns.
    Replaces matches with [REDACTED:<type>].
    """
    if not text:
        return ""

    patterns = {
        "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        # Simple IP regex, avoiding loopback/local matches might be too complex for a single regex,
        # so we redact all IPv4-looking strings to be safe foundation models don't ingest infrastructure IPs.
        "IP": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "OPENAI_KEY": r"sk-[a-zA-Z0-9]{20,}",
        "GITHUB_KEY": r"ghp_[a-zA-Z0-9]{20,}",
        "GOOGLE_KEY": r"AIza[0-9A-Za-z-_]{35}",
        "PRIVATE_KEY": r"-----BEGIN [A-Z]+ PRIVATE KEY-----",
    }
    
    scrubbed_text = text
    for label, pattern in patterns.items():
        scrubbed_text = re.sub(pattern, f"[REDACTED:{label}]", scrubbed_text)
        
    return scrubbed_text


def find_best_matching_story(files: str) -> Optional[str]:
    """
    Finds the best matching story ID for the given changed files using AI.
    
    Args:
        files: A string listing changed files.
        
    Returns:
        The matched Story ID or None if no match found.
    """
    from agent.core.ai import ai_service
    
    # 1. Gather Stories
    stories_context = ""
    for file_path in config.stories_dir.rglob("*.md"):
        title = "Unknown"
        state = "UNKNOWN"
        try:
             # Fast read headers
             content = file_path.read_text(errors="ignore")
             t_match = re.search(r"^#\s*[^:]+:\s*(.*)$", content, re.MULTILINE)
             if t_match:
                 title = t_match.group(1).strip()
             s_match = re.search(r"^## State\s*\n+([A-Z]+)", content, re.MULTILINE)
             if s_match:
                 state = s_match.group(1).strip()
        except Exception:
            pass
        stories_context += f"Story: {file_path.stem} | Title: {title} | State: {state}\n"

    if not stories_context:
        return None

    stories_context = scrub_sensitive_data(stories_context)
    cleaned_files = scrub_sensitive_data(files)

    # 2. Rules
    rules_content = scrub_sensitive_data(load_governance_context())

    # 3. Prompt
    system_prompt = """You are a Repository Governance Agent.
Your task is to identify which EXISTING User Story corresponds to a set of file changes.

INPUTS:
1. List of Changed Files
2. List of Existing Stories (ID, Title, State)
3. Governance Rules (Context)

INSTRUCTIONS:
- Analyze the changed files to determine the likely architectural scope.
- Compare against the Existing Stories.
- Select the Story ID that best fits the changes.
- Consider the 'State' of the story if relevant (COMMITTED/IN_PROGRESS preferable).
- If NO story matches well, output 'NONE'.

OUTPUT FORMAT:
Output ONLY the Story ID (e.g. 'INFRA-001') or 'NONE'.
"""
    
    user_prompt = f"""CHANGED FILES:
{cleaned_files}

EXISTING STORIES:
{stories_context}

GOVERNANCE RULES:
{rules_content[:10000]}
"""

    # 4. AI Call
    try:
        content = ai_service.complete(system_prompt, user_prompt)
        if not content:
            return None

        result = content.strip().replace("`", "")
        
        if result == "NONE":
            return None
        
        return result
    except Exception as e:
        console.print(f"[yellow]⚠️  AI Story matching failed: {e}[/yellow]")
        return None

def sanitize_id(input_str: str) -> str:
    """
    Sanitize spoken or input IDs (e.g. "Web Dash 001" -> "WEB-001")
    """
    if not input_str:
        return ""
    # Normalize
    s = input_str.upper()
    s = s.replace(" DASH ", "-").replace(" MINUS ", "-")
    # Remove all whitespace
    s = re.sub(r"\s+", "", s)
    return s


def _repair_json(text: str) -> str:
    """
    Attempt to repair common LLM JSON mistakes:
    1. Trailing commas before ] or }
    2. Unescaped newlines/tabs inside string values
    3. Single quotes instead of double quotes (simple cases)
    4. Truncated responses (unclosed brackets)
    """
    if not text:
        return text

    # 1. Remove trailing commas: ,\s*] or ,\s*}
    repaired = re.sub(r',\s*(\]|})', r'\1', text)

    # 2. Fix unescaped control characters inside JSON string values.
    #    Walk the string and escape raw newlines/tabs that appear between quotes.
    result = []
    in_string = False
    i = 0
    while i < len(repaired):
        ch = repaired[i]
        if ch == '"' and (i == 0 or repaired[i-1] != '\\'):
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\t':
            result.append('\\t')
        elif in_string and ch == '\r':
            result.append('\\r')
        else:
            result.append(ch)
        i += 1
    repaired = ''.join(result)

    # 3. Try to close truncated responses (unclosed brackets)
    open_sq = repaired.count('[') - repaired.count(']')
    open_curly = repaired.count('{') - repaired.count('}')

    # Only attempt auto-close if we're missing a small number of brackets
    if 0 < open_curly <= 3:
        # Try to cleanly truncate: find last complete object/value and close
        # First, strip any trailing partial string (unmatched quote)
        stripped = repaired.rstrip()
        if stripped and stripped[-1] not in ']}",':
            # Likely a truncated string value — close it
            stripped += '"'
            open_curly_new = stripped.count('{') - stripped.count('}')
            repaired = stripped + '}' * open_curly_new
        else:
            repaired = stripped + '}' * open_curly

    open_sq = repaired.count('[') - repaired.count(']')
    if 0 < open_sq <= 3:
        repaired = repaired.rstrip() + ']' * open_sq

    return repaired


def extract_json_from_response(response: str) -> str:
    """
    Robustly extract JSON from AI response, handling markdown code blocks
    and various formatting issues. Supports JSON arrays, objects, and
    top-level primitives (strings, numbers, booleans, null).

    Includes a repair stage for common LLM JSON mistakes (trailing commas,
    unescaped newlines, truncated responses).

    NOTE: This function intentionally exceeds the 50-line guideline.  It is a
    single-purpose, sequential extraction pipeline (stages 0-5) whose steps
    share local state (``stripped``, ``cleaned``).  Splitting into sub-functions
    would scatter control-flow without improving readability.
    """
    
    if not response:
        return ""
    
    response = response.strip()

    # 1. Try direct parsing first (best case)
    try:
        json.loads(response, strict=False)
        return response
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Extract from markdown fences
    fence_pattern = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
    match = fence_pattern.search(response)
    if match:
        candidate = match.group(1).strip()
        try:
             json.loads(candidate, strict=False)
             return candidate
        except (json.JSONDecodeError, ValueError):
             # Try repairing the fenced content
             repaired = _repair_json(candidate)
             try:
                 json.loads(repaired, strict=False)
                 return repaired
             except (json.JSONDecodeError, ValueError):
                 pass  # Fallthrough

    # 3. Aggressive Bracketing (Find outer-most { } or [ ])
    first_curly = response.find('{')
    first_square = response.find('[')
    
    search_order = []
    if first_curly != -1 and (first_square == -1 or first_curly < first_square):
        search_order = [('{', '}'), ('[', ']')]
    elif first_square != -1:
        search_order = [('[', ']'), ('{', '}')]
    else:
        return ""

    best_fallback = ""

    for open_char, close_char in search_order:
        start_idx = response.find(open_char)
        if start_idx == -1:
            continue
            
        end_indices = [
            i for i, char in enumerate(response)
            if char == close_char and i > start_idx
        ]
        
        if not end_indices:
             continue

        widest_candidate = response[start_idx : end_indices[-1] + 1]
        if not best_fallback or len(widest_candidate) > len(best_fallback):
             best_fallback = widest_candidate
        
        # Try largest candidate first, then shrink
        for end_idx in reversed(end_indices):
            candidate = response[start_idx : end_idx + 1]
            try:
                json.loads(candidate, strict=False)
                return candidate
            except (json.JSONDecodeError, ValueError):
                continue

    # 4. Repair stage — attempt to fix the best candidate we found
    if best_fallback:
        repaired = _repair_json(best_fallback)
        try:
            json.loads(repaired, strict=False)
            logger.info("JSON repair succeeded on AI response.")
            return repaired
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"JSON repair failed. First 100 chars: {best_fallback[:100]}")

    # 5. Return best_fallback as-is (caller will handle the parse error)
    return best_fallback if best_fallback else ""

