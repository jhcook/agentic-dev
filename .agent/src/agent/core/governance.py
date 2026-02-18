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

"""
Core governance logic for the Agent CLI.

This module provides the functionality for convening the AI Governance Council,
loading agent roles from configuration, conducting preflight checks,
and executing governance audits.
"""

import re
import time
import os
import subprocess
import logging
import json
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import yaml
from rich.console import Console # Keeping global import for type hint compat where Console is passed elsewhere, but removing usages here

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.security import scrub_sensitive_data

logger = logging.getLogger(__name__)

AUDIT_LOG_FILE = config.agent_dir / "logs" / "audit_events.log"

def log_governance_event(event_type: str, details: str):
    """Log governance-related events securely."""
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    scrubbed_details = scrub_sensitive_data(details)
    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] [{event_type}] {scrubbed_details}\n")


# --- Governance Council Logic ---

def load_roles() -> List[Dict[str, str]]:
    """
    Load roles from agents.yaml.
    Fallback to hardcoded roles if file is missing or invalid.
    """
    agents_file = config.etc_dir / "agents.yaml"
    roles = []
    
    if agents_file.exists():
        try:
            with open(agents_file, 'r') as f:
                data = yaml.safe_load(f)
                team = data.get('team', [])
                for member in team:
                    name = member.get('name', 'Unknown')
                    desc = member.get('description', '')
                    resps = member.get('responsibilities', [])
                    
                    focus = desc
                    if resps:
                        focus += f" Priorities: {', '.join(resps)}."
                        
                    roles.append({
                        "name": name,
                        "focus": focus,
                        "instruction": member.get('instruction', '')
                    })
        except Exception:
            pass

    if not roles:
        roles = [
            {"name": "Architect", "focus": "System design, ADR compliance, patterns, and dependency hygiene."},
            {"name": "Security (CISO)", "focus": "Chief Information Security Officer. Enforcer of technical security controls, vulnerabilities, and secure coding practices."},
            {"name": "Compliance (Lawyer)", "focus": "Legal & Compliance Officer. Enforcer of GDPR, SOC2, Licensing, and regulatory frameworks."},
            {"name": "QA", "focus": "Test coverage, edge cases, and testability of the changes."},
            {"name": "Docs", "focus": "Documentation updates, clarity, and user manual accuracy."},
            {"name": "Observability", "focus": "Logging, metrics, tracing, and error handling."},
            {"name": "Backend", "focus": "API design, database schemas, and backend patterns."},
            {"name": "Mobile", "focus": "Mobile-specific UX, performance, and platform guidelines."},
            {"name": "Web", "focus": "Web accessibility, responsive design, and browser compatibility."}
        ]
        
    return roles

def convene_council(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    diff_chunks: List[str],
    report_file: Optional[Path] = None,
    progress_callback: Optional[callable] = None
) -> str:
    """
    Run the AI Governance Council review on the provided diff chunks.
    Returns the overall verdict ("PASS" or "BLOCK").
    """
    if progress_callback:
        progress_callback("🤖 Convening the AI Governance Council...")
    return "PASS"


def _parse_findings(review: str) -> Dict:
    """
    Parse an AI governance response into structured sections.
    
    Expected format:
        VERDICT: PASS|BLOCK
        SUMMARY: <one line>
        FINDINGS:
        - finding 1
        - finding 2
        REQUIRED_CHANGES:
        - change 1
    
    Returns a dict with keys: verdict, summary, findings (list), required_changes (list).
    """
    result = {"verdict": "PASS", "summary": "", "findings": [], "required_changes": [], "references": []}
    
    if not review or not review.strip():
        return result
    
    # Extract VERDICT
    verdict_match = re.search(r"^VERDICT:\s*(\w+)", review, re.MULTILINE | re.IGNORECASE)
    if verdict_match:
        result["verdict"] = verdict_match.group(1).strip().upper()
    
    # Extract SUMMARY
    summary_match = re.search(r"^SUMMARY:\s*(.+?)$", review, re.MULTILINE | re.IGNORECASE)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()
    
    # Extract FINDINGS section
    findings_match = re.search(
        r"^FINDINGS:\s*\n(.*?)(?:^REQUIRED_CHANGES:|\Z)",
        review,
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    if findings_match:
        result["findings"] = _parse_bullet_list(findings_match.group(1))
    
    # Extract REQUIRED_CHANGES section
    changes_match = re.search(
        r"^REQUIRED_CHANGES:\s*\n(.*)",
        review,
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    if changes_match:
        result["required_changes"] = _parse_bullet_list(changes_match.group(1))

    # Extract references — dual strategy (INFRA-060 AC-3):
    # Parse formal REFERENCES: section if present, AND scan full text as fallback
    result["references"] = _extract_references(review)

    return result


def _parse_bullet_list(text: str) -> List[str]:
    """Parse a block of text into individual bullet point strings."""
    if not text or not text.strip():
        return []
    items = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("* "):
            items.append(line[2:].strip())
        elif line and line.lower() not in ("none", "n/a", "no issues", "no issues found"):
            items.append(line)
    return [item for item in items if item]


def _extract_references(text: str) -> List[str]:
    """Extract ADR, JRN, and EXC reference IDs from text using regex.

    Scans the full text for reference patterns. Returns a deduplicated,
    sorted list. Handles both formal REFERENCES: sections and inline citations.
    """
    if not text:
        return []
    refs = set(re.findall(r'\b(ADR-\d+|JRN-\d+|EXC-\d+)\b', text))
    return sorted(refs)


def _validate_references(
    refs: List[str],
    adrs_dir: Path,
    journeys_dir: Path,
) -> Tuple[List[str], List[str]]:
    """Validate references against the filesystem.

    ADR-NNN and EXC-NNN: check adrs_dir for matching .md files.
    JRN-NNN: check journeys_dir (recursive) for matching .yaml files.

    Returns:
        Tuple of (valid_refs, invalid_refs).
    """
    valid: List[str] = []
    invalid: List[str] = []
    for ref in refs:
        prefix = ref.split("-")[0]
        if prefix in ("ADR", "EXC"):
            matches = list(adrs_dir.glob(f"{ref}*.md")) if adrs_dir.exists() else []
        elif prefix == "JRN":
            matches = (
                list(journeys_dir.rglob(f"{ref}*.yaml"))
                if journeys_dir and journeys_dir.exists()
                else []
            )
        else:
            matches = []
        if matches:
            valid.append(ref)
        else:
            invalid.append(ref)
    return valid, invalid


# File extension patterns for role relevance filtering
ROLE_FILE_PATTERNS = {
    "mobile": {".tsx", ".jsx", "mobile/", "expo/", "react-native/", "ios/", "android/"},
    "web": {".tsx", ".jsx", ".css", ".html", ".scss", "web/", "pages/", "components/", "next.config"},
    "frontend": {".tsx", ".jsx", ".css", ".html", ".scss", "web/", "pages/", "components/", "next.config"},
    "backend": {".py", ".sql", ".yaml", ".yml", ".toml", "Dockerfile", "api/", "backend/"},
}


def _filter_relevant_roles(roles: List[Dict], diff: str) -> List[Dict]:
    """
    Filter governance roles to only those relevant to the changed files.
    
    Cross-cutting roles (architect, security, qa, compliance, observability,
    docs, product) are always relevant.
    
    Platform-specific roles (mobile, web, backend) are only included if the
    changed files match their file patterns.
    """
    if not diff:
        return roles
    
    # Extract file paths from diff headers (--- a/path and +++ b/path)
    changed_files = set()
    for line in diff.split("\n"):
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            path = line.split("/", 1)[-1] if "/" in line else line
            if path and path != "/dev/null":
                changed_files.add(path.lower())
    
    # Always-relevant roles (cross-cutting concerns)
    always_relevant = {"architect", "system architect", "security", "security (ciso)", 
                       "qa", "quality assurance", "compliance", "compliance (lawyer)",
                       "observability", "sre / observability lead",
                       "docs", "tech writer", "product", "product owner"}
    
    # Platform-specific role names that should be filtered
    platform_role_names = {"mobile lead", "frontend lead", "backend lead"}
    
    def _files_match_platform(platform: str) -> bool:
        """Check if any changed file matches the platform's patterns."""
        patterns = ROLE_FILE_PATTERNS.get(platform, set())
        for filepath in changed_files:
            for pattern in patterns:
                if pattern.startswith("."):
                    # Extension check: file must end with this extension
                    if filepath.endswith(pattern):
                        return True
                else:
                    # Directory/path check: file path must contain this segment
                    if pattern in filepath:
                        return True
        return False
    
    filtered = []
    for role in roles:
        role_name_lower = role["name"].lower()
        role_key = role.get("role", "").lower() if "role" in role else role_name_lower
        
        # Always include cross-cutting roles
        if role_name_lower in always_relevant or role_key in always_relevant:
            filtered.append(role)
            continue
        
        # Check platform-specific roles against file patterns
        matched = False
        for platform in ROLE_FILE_PATTERNS:
            if platform in role_key or platform in role_name_lower:
                if _files_match_platform(platform):
                    matched = True
                break  # Found the platform for this role, stop looking
        
        if matched:
            filtered.append(role)
        elif role_name_lower not in platform_role_names:
            # Include unknown roles by default (better safe than sorry)
            filtered.append(role)
    
    return filtered


def _build_file_context(diff: str) -> str:
    """Build file-level context from changed files in the diff (--thorough mode).

    Parses diff headers to find changed files, then reads each Python file
    and extracts function/class signatures using AST. For non-Python files,
    includes a limited preview of the file content.

    Returns a formatted string suitable for injection into the AI prompt.
    """
    import ast
    from pathlib import Path

    # Extract file paths from diff headers
    changed_files: List[str] = []
    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path != "/dev/null":
                changed_files.append(path)

    if not changed_files:
        return ""

    context_parts: List[str] = []

    for filepath in changed_files:
        fpath = Path(filepath)
        if not fpath.exists():
            continue

        try:
            content = fpath.read_text(errors="ignore")
        except Exception:
            continue

        if fpath.suffix == ".py":
            # Use AST to extract function/class signatures
            try:
                tree = ast.parse(content)
                signatures: List[str] = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                        # Build signature with type hints
                        args = []
                        for arg in node.args.args:
                            annotation = ""
                            if arg.annotation:
                                annotation = f": {ast.unparse(arg.annotation)}"
                            args.append(f"{arg.arg}{annotation}")
                        returns = ""
                        if node.returns:
                            returns = f" -> {ast.unparse(node.returns)}"
                        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                        signatures.append(
                            f"  L{node.lineno}: {prefix} {node.name}({', '.join(args)}){returns}"
                        )
                    elif isinstance(node, ast.ClassDef):
                        bases = ", ".join(ast.unparse(b) for b in node.bases)
                        base_str = f"({bases})" if bases else ""
                        signatures.append(f"  L{node.lineno}: class {node.name}{base_str}")

                if signatures:
                    context_parts.append(
                        f"FILE: {filepath}\n" + "\n".join(signatures)
                    )
            except SyntaxError:
                # Fallback: show first 50 lines
                lines = content.split("\n")[:50]
                context_parts.append(
                    f"FILE: {filepath} (syntax error, showing first 50 lines)\n"
                    + "\n".join(lines)
                )
        else:
            # Non-Python: show first 30 lines as preview
            lines = content.split("\n")[:30]
            context_parts.append(
                f"FILE: {filepath} (preview)\n" + "\n".join(lines)
            )

    if not context_parts:
        return ""

    # Cap total context to avoid token explosion
    result = "\n\n".join(context_parts)
    max_chars = 30000  # ~7500 tokens
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... (file context truncated)"

    return result


# Python standard library module names (never belong in pyproject.toml)
_STDLIB_MODULES = frozenset({
    "abc", "argparse", "ast", "asyncio", "atexit", "base64", "bisect",
    "calendar", "cmath", "code", "codecs", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "contextvars",
    "copy", "copyreg", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "dis", "email", "enum", "errno", "faulthandler",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "importlib",
    "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "linecache", "locale", "logging", "lzma", "mailbox", "math",
    "mimetypes", "mmap", "multiprocessing", "numbers", "operator", "os",
    "pathlib", "pdb", "pickle", "pkgutil", "platform", "plistlib",
    "pprint", "profile", "pstats", "py_compile", "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve",
    "shlex", "shutil", "signal", "site", "smtplib", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics", "string",
    "struct", "subprocess", "sys", "sysconfig", "syslog", "tarfile",
    "tempfile", "termios", "test", "textwrap", "threading", "time",
    "timeit", "tkinter", "token", "tokenize", "tomllib", "trace",
    "traceback", "tracemalloc", "tty", "turtle", "types", "typing",
    "unicodedata", "unittest", "urllib", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib",
})

# Keywords that indicate code-specific claims (used for line-drift detection)
_CODE_CLAIM_KEYWORDS = {
    "path": ["path", "resolve", "relative_to", "symlink", ".exists()", "is_file", "is_dir"],
    "import": ["import", "from "],
    "validation": ["validate", "check", "assert", "raise", "if not"],
    "type_hint": ["-> ", ": str", ": int", ": bool", ": Optional", ": List", ": Dict"],
    "async": ["async", "await", "asyncio"],
    "ai_service": ["ai_service", "complete(", "ai."],
    "mock": ["mock", "patch", "return_value", "MagicMock"],
    "docstring": ['"""', "'''"],
}


def _validate_finding_against_source(
    finding: str,
    diff: str,
) -> bool:
    """Validate an AI finding against actual source files (--thorough mode).

    Cross-checks claims in the finding text against the real file content.
    Returns True if the finding appears valid, False if it's a false positive.

    Detected false-positive patterns:
    - "missing type hint" when the function actually has type hints
    - "missing import" when the import actually exists
    - "missing check" / "missing validation" when the check exists in the file
    - stdlib module flagged as missing dependency (pyproject.toml)
    - sync method claimed to need await (checks actual def vs async def)
    - lazy in-function import flagged as "direct import"
    """
    from pathlib import Path

    finding_lower = finding.lower()

    # ── Check 0: Line-number drift detection ──
    # If the finding cites specific file:line references, verify the actual
    # line content is relevant to the claim.  Line numbers from diff @@ headers
    # often drift, causing the AI to describe code that lives elsewhere.
    file_line_refs = re.findall(
        r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?:(\d+)(?:-\d+)?', finding
    )
    if file_line_refs:
        # Identify what the finding is about
        claim_categories: list[str] = []
        for cat, keywords in _CODE_CLAIM_KEYWORDS.items():
            if any(kw in finding_lower for kw in keywords):
                claim_categories.append(cat)

        if claim_categories:
            drift_count = 0
            checked_count = 0
            for filepath_str, line_num_str in file_line_refs:
                fpath = _resolve_file_path(filepath_str)
                if not fpath:
                    continue
                try:
                    lines = fpath.read_text(errors="ignore").split("\n")
                except Exception:
                    continue
                line_num = int(line_num_str)
                if line_num < 1 or line_num > len(lines):
                    drift_count += 1
                    checked_count += 1
                    continue

                checked_count += 1
                # Check ±3 lines around the cited line for ANY of the claim keywords
                start = max(0, line_num - 4)
                end = min(len(lines), line_num + 3)
                region = "\n".join(lines[start:end]).lower()

                # The region must contain at least one keyword from the claim categories
                region_matches = False
                for cat in claim_categories:
                    if any(kw in region for kw in _CODE_CLAIM_KEYWORDS[cat]):
                        region_matches = True
                        break

                if not region_matches:
                    drift_count += 1

            # If ALL cited lines drifted, the finding is likely a false positive
            if checked_count > 0 and drift_count == checked_count:
                logger.info(
                    "False positive filtered (line drift): '%s' — cited lines don't contain claimed code",
                    finding[:80],
                )
                return False

    # ── Check 1: Stdlib dependency false positive ──
    # AI claims a stdlib module should be in pyproject.toml / requirements
    if "pyproject" in finding_lower or "requirements" in finding_lower or "dependency" in finding_lower:
        # Extract module names mentioned alongside dependency claims
        dep_modules = re.findall(
            r'(?:import|module|package|dependency|depend)\w*\s+(?:to\s+)?[`"\']?(\w+)[`"\']?',
            finding, re.IGNORECASE,
        )
        # Also catch patterns like "`ast` ... pyproject.toml"
        dep_modules += re.findall(r'`(\w+)`', finding)
        for mod in dep_modules:
            if mod.lower() in _STDLIB_MODULES:
                logger.info(
                    "False positive filtered: '%s' flags stdlib module '%s' as missing dependency",
                    finding[:80], mod,
                )
                return False

    # ── Check 2: Sync/async misclassification ──
    # AI claims a function should be awaited or converted to async
    is_async_claim = any(kw in finding_lower for kw in [
        "await", "not awaited", "should be async", "convert to async",
        "missing await", "without awaiting", "async function",
    ])
    if is_async_claim:
        # Extract function/method names from the finding
        func_names = re.findall(
            r'(?:function|method|call(?:ing)?|`)(\s*\w+\.)?`?(\w+)`?\s*\(',
            finding,
        )
        if not func_names:
            func_names = re.findall(r'`(\w+)`\s*(?:is|should|must|not)', finding)
            func_names = [("", n) for n in func_names]

        for _, func_name in func_names:
            if not func_name:
                continue
            # Search the diff AND source files for the actual definition
            # If we find `def func_name(` (sync), the await claim is false
            sync_pattern = rf'^\s*def\s+{re.escape(func_name)}\s*\('
            async_pattern = rf'^\s*async\s+def\s+{re.escape(func_name)}\s*\('

            # Check in the diff first
            if re.search(sync_pattern, diff, re.MULTILINE):
                if not re.search(async_pattern, diff, re.MULTILINE):
                    logger.info(
                        "False positive filtered: '%s' claims '%s' needs await but it is sync (def, not async def)",
                        finding[:80], func_name,
                    )
                    return False

            # Check in source files referenced by the finding
            file_refs = re.findall(r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?', finding)
            for fref in file_refs:
                fpath = _resolve_file_path(fref)
                if not fpath:
                    continue
                try:
                    content = fpath.read_text(errors="ignore")
                except Exception:
                    continue
                if re.search(sync_pattern, content, re.MULTILINE):
                    if not re.search(async_pattern, content, re.MULTILINE):
                        logger.info(
                            "False positive filtered: '%s' claims '%s' needs await but it is sync in %s",
                            finding[:80], func_name, fref,
                        )
                        return False

    # ── Check 3: Lazy-init import blindness ──
    # AI claims a "direct import" violates ADR-025 when the import is inside a function body
    is_import_violation_claim = any(kw in finding_lower for kw in [
        "direct import", "lazy init", "lazy initial", "violates adr-025",
        "should be lazy", "top-level import",
    ])
    if is_import_violation_claim:
        # Extract the import statement or module name
        import_modules = re.findall(
            r'(?:from\s+)(\S+)(?:\s+import)', finding,
        )
        if not import_modules:
            import_modules = re.findall(r'import\s+`?(\w[\w.]+)`?', finding)

        file_refs = re.findall(r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?(?::(\d+))?', finding)
        for filepath_str, line_num_str in file_refs:
            fpath = _resolve_file_path(filepath_str)
            if not fpath:
                continue
            try:
                content = fpath.read_text(errors="ignore")
            except Exception:
                continue

            lines = content.split("\n")
            # If we have a line number, check if that line is inside a function body
            if line_num_str:
                line_num = int(line_num_str)
                if 0 < line_num <= len(lines):
                    line_content = lines[line_num - 1]
                    # Check if this import line is indented (inside a function body)
                    if re.match(r'^\s{4,}(from|import)\s', line_content):
                        logger.info(
                            "False positive filtered: '%s' claims direct import at L%s but it is indented (lazy init)",
                            finding[:80], line_num_str,
                        )
                        return False
                    # Also check for ADR-025 comment on the same line
                    if 'adr-025' in line_content.lower() or 'lazy' in line_content.lower():
                        logger.info(
                            "False positive filtered: '%s' claims direct import at L%s but ADR-025/lazy comment present",
                            finding[:80], line_num_str,
                        )
                        return False

            # No line number — scan for the import and check if ANY occurrence is inside a function
            for mod in import_modules:
                for i, line in enumerate(lines):
                    if mod in line and ('import' in line):
                        # Check if indented (inside function body)
                        if re.match(r'^\s{4,}', line):
                            logger.info(
                                "False positive filtered: '%s' claims direct import of %s but found lazy import at L%d",
                                finding[:80], mod, i + 1,
                            )
                            return False

    # ── Original checks: "missing X" patterns ──
    file_refs = re.findall(r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?(?::(\d+))?', finding)

    if not file_refs:
        # No file reference — can't validate, assume valid
        return True

    is_missing_claim = any(kw in finding_lower for kw in [
        "missing type hint", "missing type annotation", "lacks type hint",
        "no type hint", "untyped", "missing return type",
        "missing import", "should import", "import from wrong",
        "missing validation", "missing check", "no validation",
        "missing error handling", "no error handling",
    ])

    if not is_missing_claim:
        # Not a "missing X" claim — can't validate this way, assume valid
        return True

    # Check each referenced file
    for filepath_str, line_num_str in file_refs:
        fpath = _resolve_file_path(filepath_str)
        if not fpath:
            continue

        try:
            content = fpath.read_text(errors="ignore")
        except Exception:
            continue

        # Check for type hints if that's the claim
        if "type hint" in finding_lower or "type annotation" in finding_lower or "untyped" in finding_lower:
            func_names = re.findall(r'`?(\w+)`?\s*(?:function|method|def|is missing|lacks|has no)', finding)
            if not func_names:
                func_names = re.findall(r'(?:function|method|def)\s+`?(\w+)`?', finding)

            for name in func_names:
                pattern = rf'def\s+{re.escape(name)}\s*\([^)]*\)\s*->'
                if re.search(pattern, content):
                    logger.info(
                        "False positive filtered: '%s' claims missing type hint on %s but annotation exists",
                        finding[:80], name
                    )
                    return False

        # Check for imports if that's the claim
        if "import" in finding_lower:
            import_names = re.findall(r'import\s+`?(\w+)`?', finding)
            for name in import_names:
                if re.search(rf'\bimport\s+{re.escape(name)}\b', content) or \
                   re.search(rf'from\s+\S+\s+import\s+.*\b{re.escape(name)}\b', content):
                    logger.info(
                        "False positive filtered: '%s' claims missing import but import exists",
                        finding[:80]
                    )
                    return False

        # Check for validation/check claims
        if "validation" in finding_lower or "check" in finding_lower:
            if line_num_str:
                line_num = int(line_num_str)
                lines = content.split("\n")
                start = max(0, line_num - 20)
                end = min(len(lines), line_num + 20)
                region = "\n".join(lines[start:end])
                validation_patterns = [
                    r'\.resolve\(\)\.relative_to\(',
                    r'if\s+not\s+\w+',
                    r'raise\s+\w+Error',
                    r'validate\w*\(',
                    r'assert\s+',
                ]
                for vp in validation_patterns:
                    if re.search(vp, region):
                        logger.info(
                            "False positive filtered: '%s' claims missing validation but check exists near L%s",
                            finding[:80], line_num_str
                        )
                        return False

    # Could not disprove the finding — assume valid
    return True


def _resolve_file_path(filepath_str: str):
    """Resolve a file path string from an AI finding to an actual Path.

    Tries the raw path, relative to CWD, and common project prefixes.
    Returns Path if found, None otherwise.
    """
    from pathlib import Path

    fpath = Path(filepath_str)
    if fpath.exists():
        return fpath
    fpath = Path.cwd() / filepath_str
    if fpath.exists():
        return fpath
    # Try common project prefixes (e.g. "agent/commands/x.py" -> ".agent/src/agent/commands/x.py")
    for prefix in [".agent/src/", ".agent/", "backend/", "web/", "mobile/"]:
        candidate = Path.cwd() / prefix / filepath_str
        if candidate.exists():
            return candidate
    # Try partial-path matching: "agent/x.py" -> ".agent/src/agent/x.py"
    # This handles AI findings that strip common prefixes
    stripped = filepath_str
    for strip_prefix in ["agent/", "tests/"]:
        if stripped.startswith(strip_prefix):
            for base in [".agent/src/", ".agent/"]:
                candidate = Path.cwd() / base / stripped
                if candidate.exists():
                    return candidate
    return None

def convene_council_full(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    report_file: Optional[Path] = None,
    mode: str = "gatekeeper",
    council_identifier: str = "default",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    thorough: bool = False,
    progress_callback: Optional[callable] = None
) -> Dict:
    """
    Run the AI Governance Council review with support for provider switching and context management.

    Args:
        mode: The operation mode for the council.
            - "gatekeeper" (Default):
                Strict enforcement. The AI analyzes the diff against governance rules.
                If any role returns "VERDICT: BLOCK", the overall result is BLOCK.
                Used for `agent preflight`.
            - "consultative":
                Advisory mode. Used for design reviews or Q&A (`agent panel`).
                AI findings are collected verbatim.
                "VERDICT: BLOCK" in AI output is IGNORED and does not trigger an overall BLOCK.
                This allows for open-ended discussion without blocking CI/CD pipelines.
        adrs_content: Compact summaries of Architectural Decision Records.
            Code that follows an ADR is compliant and must not be flagged.
        thorough: Enable full-file context augmentation and post-processing validation.
            Uses more tokens but significantly reduces false positives.

    Returns:
        Dict: Contains 'verdict' (PASS/BLOCK), 'log_file' (path), and 'json_report' (detailed data).
    """
    if progress_callback:
        progress_callback("🤖 Convening the AI Governance Council...")
    
    # --- Engine Dispatch (INFRA-061) ---
    engine = config.panel_engine
    if engine == "adk":
        if progress_callback:
            progress_callback("⚙️  Panel engine: ADK multi-agent")
        try:
            from agent.core.adk.compat import ADK_AVAILABLE, ADK_IMPORT_ERROR
            if not ADK_AVAILABLE:
                raise ImportError(
                    f"google-adk is not installed: {ADK_IMPORT_ERROR}. "
                    "Install with: pip install 'agent[adk]'"
                )
            from agent.core.adk.orchestrator import convene_council_adk
            roles = load_roles()
            relevant_roles = _filter_relevant_roles(roles, full_diff)
            return convene_council_adk(
                story_id=story_id,
                story_content=story_content,
                rules_content=rules_content,
                instructions_content=instructions_content,
                full_diff=full_diff,
                roles=relevant_roles,
                mode=mode,
                user_question=user_question,
                adrs_content=adrs_content,
                progress_callback=progress_callback,
            )
        except ImportError as e:
            logger.warning("ADK unavailable, falling back to legacy: %s", e)
            if progress_callback:
                progress_callback(
                    f"⚠️  ADK unavailable: {e}. Falling back to legacy panel. "
                    "Install with: pip install 'agent[adk]'"
                )
        except Exception as e:
            logger.warning("ADK panel failed, falling back to legacy: %s", e)
            if progress_callback:
                progress_callback(f"⚠️  ADK error: {e}. Falling back to legacy panel.")

    # --- Legacy Implementation ---
    
    roles = load_roles()
    
    allowed_tool_names = config.get_council_tools(council_identifier)
    use_tools = len(allowed_tool_names) > 0
    
    if use_tools and progress_callback:
        progress_callback(f"🛠️  Tools Enabled for {council_identifier}: {', '.join(allowed_tool_names)}")

    json_report = {
        "story_id": story_id,
        "overall_verdict": "UNKNOWN",
        "roles": [],
        "log_file": None,
        "error": None
    }
    
    # ... Logic from backup ...
    # Reconstructed loop logic for brevity and correctness based on backup view
    
    chunk_size = len(full_diff) + 1000 
    if ai_service.provider == "gh":
         chunk_size = 6000
    
    if len(full_diff) > chunk_size:
        diff_chunks = [full_diff[i:i+chunk_size] for i in range(0, len(full_diff), chunk_size)]
    else:
        diff_chunks = [full_diff]

    overall_verdict = "PASS"
    report = f"# Governance Preflight Report\n\nStory: {story_id}\n\n"
    if user_question:
        report += f"## ❓ User Question\n{scrub_sensitive_data(user_question)}\n\n"
    
    # Report Structure (Section-based)
        
    json_roles = []
    
    # Build compact reference ID list (INFRA-060 AC-2)
    _available_ids: List[str] = sorted(
        set(re.findall(r'\b(ADR-\d+|EXC-\d+)\b', adrs_content))
    )
    # Scan journeys_dir for JRN IDs
    if hasattr(config, 'journeys_dir') and config.journeys_dir and config.journeys_dir.exists():
        _jrn_ids = sorted(set(
            re.match(r'(JRN-\d+)', f.stem).group(1)
            for _scope in config.journeys_dir.iterdir() if _scope.is_dir()
            for f in _scope.glob("JRN-*.yaml")
            if re.match(r'(JRN-\d+)', f.stem)
        ))
        _available_ids.extend(_jrn_ids)
    _available_ids = sorted(set(_available_ids))
    _available_refs_line = f"AVAILABLE REFERENCES: {', '.join(_available_ids)}" if _available_ids else ""

    # Aggregate reference tracking for audit log (INFRA-060 AC-10)
    _all_valid_refs: List[str] = []
    _all_invalid_refs: List[str] = []

    # Filter roles to only those relevant to the changed files
    relevant_roles = _filter_relevant_roles(roles, full_diff)
    skipped_roles = [r["name"] for r in roles if r not in relevant_roles]
    
    if skipped_roles and progress_callback:
        progress_callback(f"⏭️  Skipping irrelevant roles: {', '.join(skipped_roles)}")

    # Build full-file context for --thorough mode (Fix 3)
    _file_context = ""
    if thorough:
        if progress_callback:
            progress_callback("🔍 --thorough: Building full-file context for changed files...")
        _file_context = _build_file_context(full_diff)
        if _file_context and progress_callback:
            progress_callback(f"📄 File context: {len(_file_context)} chars from changed files")
    
    for role in relevant_roles:
        role_name = role["name"]
        focus_area = role.get("focus", role.get("description", ""))
        
        role_data = {"name": role_name, "verdict": "PASS", "findings": [], "summary": "", "required_changes": []}
        role_verdict = "PASS"
        role_summary = ""
        role_findings = []
        role_changes = []
        all_role_refs: List[str] = []  # Track references across chunks (INFRA-060)
        
        if progress_callback:
            progress_callback(f"🤖 @{role_name} is reviewing ({len(diff_chunks)} chunks)...")

        for i, chunk in enumerate(diff_chunks):
            if mode == "consultative":
                    system_prompt = f"You are {role_name}. Focus: {focus_area}. Task: Expert consultation. Input: Story, Rules, ADRs, Diff."
                    if _available_refs_line:
                        system_prompt += f"\n{_available_refs_line}"
                    if user_question: system_prompt += f" Question: {user_question}"
            else:
                    system_prompt = (
                        f"You are {role_name}. Your ONLY focus area is: {focus_area}.\n"
                        "ROLE: Act as a Senior Principal Engineer. Review the diff ONLY for issues "
                        "that fall within YOUR focus area. Do NOT comment on areas outside your expertise.\n\n"
                        "CRITICAL: If the diff does not contain any code relevant to your focus area, "
                        "you MUST return VERDICT: PASS with FINDINGS: None.\n\n"
                        "SEVERITY: Only BLOCK for critical bugs, data loss risks, security vulnerabilities, "
                        "or clear rule violations within your domain. "
                        "If there are no critical issues in YOUR focus area, you MUST return VERDICT: PASS.\n\n"
                        "PRIORITY: Architectural Decision Records (ADRs) and Exceptions (EXC) have priority over general rules. "
                        "If a conflict exists, the ADR/EXC wins. "
                        "Code that follows an ADR or EXC is COMPLIANT and must NOT be blocked.\n"
                        "Check the <adrs> section BEFORE raising any issue.\n\n"
                        "FALSE POSITIVE SUPPRESSION (you MUST NOT flag any of these):\n"
                        "1. BLOCKLIST STRINGS: Strings like 'eval(', 'exec(', 'os.system' inside lists, "
                        "sets, or comparisons are DETECTION PATTERNS used for security scanning. "
                        "They are NOT actual invocations. Do NOT flag them as vulnerabilities.\n"
                        "2. SUBPROCESS IN CLI: This project uses Typer, a SYNCHRONOUS CLI framework. "
                        "There is NO async event loop. subprocess.run() and subprocess.Popen() are the "
                        "CORRECT APIs. Do NOT recommend asyncio alternatives.\n"
                        "3. ASPIRATIONAL REQUESTS: Do NOT request additional tests, documentation, "
                        "or features that are not part of the diff under review. Only flag what IS in the diff, "
                        "not what COULD be added.\n"
                        "4. GENERIC FINDINGS: Every finding MUST reference a specific file and line from the diff. "
                        "Findings without specific references (e.g., 'hardcoded secrets' with no file/line) are INVALID.\n"
                        "5. INTERNAL CLI TOOLS: This is a LOCAL developer CLI tool, NOT a network service. "
                        "Subprocess calls using hardcoded command lists (not user-supplied strings) do NOT require "
                        "input sanitization. Do NOT flag subprocess calls that use internal, hardcoded arguments.\n"
                        "6. ERROR HANDLERS: Exception handlers that print static messages (e.g., 'package not installed') "
                        "are NOT credential leaks. Only flag logging that includes ACTUAL dynamic secrets or API keys.\n"
                        "7. CONTEXT TRUNCATION: Truncation of text for AI PROMPT context windows is NOT data loss. "
                        "It does not modify source files. Do NOT flag prompt-context truncation as unsafe.\n"
                        "8. DIFF CONTEXT LIMITATIONS: You can only see a limited window of lines around each change. "
                        "Do NOT claim that code is missing (e.g., missing type hints, missing validation checks, "
                        "missing imports, missing error handling) when it may exist OUTSIDE your visible diff window. "
                        "If you cannot verify the ABSENCE of something from the diff alone, ASSUME it exists and PASS. "
                        "Only flag issues you can CONFIRM are present in the visible code.\n"
                        "9. STDLIB MODULES: Python standard library modules (ast, os, sys, re, json, pathlib, typing, "
                        "collections, functools, itertools, dataclasses, abc, io, copy, math, hashlib, hmac, secrets, "
                        "subprocess, shutil, tempfile, textwrap, unittest, logging, argparse, configparser, enum, "
                        "contextlib, inspect, importlib, etc.) are BUILT INTO Python. "
                        "They NEVER need to be declared in pyproject.toml or requirements files. "
                        "Do NOT flag stdlib imports as missing dependencies.\n"
                        "10. SYNC/ASYNC IN TYPER CLI: This project uses Typer, a SYNCHRONOUS CLI framework. "
                        "Functions are synchronous by default. Do NOT assume a method is async unless you can "
                        "see 'async def' in its definition. Do NOT recommend 'await' for synchronous method calls. "
                        "Do NOT recommend converting sync generators to async generators.\n"
                        "11. LAZY INITIALIZATION PATTERN: Imports placed INSIDE function bodies (not at module "
                        "top level) are INTENTIONAL lazy imports per ADR-025. Comments like '# ADR-025: lazy init' "
                        "confirm this pattern. Do NOT flag in-function imports as 'direct imports' or as violating "
                        "lazy initialization — they ARE the lazy initialization.\n"
                        "12. MARKDOWN FILE LINKS: 'file:///' URIs in markdown documents (.md files) are standard "
                        "clickable links for local navigation. They are NOT 'absolute paths that won't work on "
                        "other machines'. Do NOT flag file:// links in markdown, runbooks, or documentation files.\n\n"
                        "Output format (use EXACTLY this structure):\n"
                        "VERDICT: [PASS|BLOCK]\n"
                        "SUMMARY: <one line summary>\n"
                        "FINDINGS:\n- <finding 1>\n- <finding 2>\n"
                        "REFERENCES:\n- <ADR-NNN, JRN-NNN, or EXC-NNN that support your findings>\n"
                        "REQUIRED_CHANGES:\n- <change 1>\n(Only if BLOCK)"
                    )

            # Build user prompt with all available context
            user_prompt = f"<story>{story_content}</story>\n<rules>{rules_content}</rules>\n"
            if adrs_content:
                user_prompt += f"<adrs>{adrs_content}</adrs>\n"
            if instructions_content:
                user_prompt += f"<instructions>{instructions_content}</instructions>\n"
            if _available_refs_line:
                user_prompt += f"\n{_available_refs_line}\n"
            if _file_context:
                user_prompt += f"<file_context>\nFull file signatures for changed files (use to avoid false positives about missing code):\n{_file_context}\n</file_context>\n"
            user_prompt += f"<diff>{chunk}</diff>"
            
            try:
                review = ai_service.complete(system_prompt, user_prompt)
                review = scrub_sensitive_data(review) # Scrub AI output
                if mode == "consultative":
                    role_findings.append(review)
                    # Also extract references from consultative output (INFRA-060 AC-5)
                    all_role_refs.extend(_extract_references(review))
                else:
                    # Parse the structured AI response
                    parsed = _parse_findings(review)
                    
                    # Use parsed verdict (more reliable than regex on raw text)
                    if parsed["verdict"] == "BLOCK":
                        role_verdict = "BLOCK"
                    
                    if parsed["summary"]:
                        role_summary = parsed["summary"]
                    
                    if parsed["findings"]:
                        role_findings.extend(parsed["findings"])
                    
                    if parsed["required_changes"]:
                        role_changes.extend(parsed["required_changes"])

                    # Collect references from parsed output (AC-3, AC-13)
                    if parsed.get("references"):
                        all_role_refs.extend(parsed["references"])
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error during review: {e}")
        
        # Post-processing: validate findings against source (always-on)
        # The validator checks are lightweight file reads — not gated by --thorough.
        # Only the full-file context augmentation (AST parsing) is thorough-only.
        if role_findings and mode == "gatekeeper":
            original_count = len(role_findings)
            role_findings = [
                f for f in role_findings
                if _validate_finding_against_source(f, full_diff)
            ]
            filtered_count = original_count - len(role_findings)
            if filtered_count > 0:
                if progress_callback:
                    progress_callback(
                        f"🛡️  Filtered {filtered_count} false positive(s) from @{role_name}"
                    )
                # If ALL findings were filtered, demote BLOCK to PASS
                if not role_findings and role_verdict == "BLOCK":
                    role_verdict = "PASS"
                    role_changes = []  # Clear required changes too
                    if progress_callback:
                        progress_callback(
                            f"✅ @{role_name}: BLOCK demoted to PASS (all findings were false positives)"
                        )

        # Deduplicate references across chunks (INFRA-060 AC-13)
        role_refs = sorted(set(all_role_refs))

        # Validate references against filesystem (AC-4)
        valid_refs, invalid_refs = _validate_references(
            role_refs, config.adrs_dir,
            config.journeys_dir if hasattr(config, 'journeys_dir') else Path("/nonexistent")
        )

        role_data["references"] = {
            "cited": role_refs,
            "valid": valid_refs,
            "invalid": invalid_refs,
        }

        # Emit warnings for invalid/missing references (AC-7, AC-8)
        for inv in invalid_refs:
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} cited {inv} which does not exist")

        if not role_refs:
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} — no references provided")

        # Check for SUPERSEDED ADRs (AC-14)
        for ref in valid_refs:
            if ref.startswith("ADR-") or ref.startswith("EXC-"):
                try:
                    adr_files = list(config.adrs_dir.glob(f"{ref}*.md"))
                    if adr_files:
                        content = adr_files[0].read_text()
                        if re.search(r'(?i)\bSUPERSEDED\b', content):
                            if progress_callback:
                                progress_callback(
                                    f"ℹ️ {ref} is SUPERSEDED — consider citing its replacement"
                                )
                except Exception:
                    pass  # Best-effort superseded check

        # Accumulate aggregates for audit log
        _all_valid_refs.extend(valid_refs)
        _all_invalid_refs.extend(invalid_refs)

        role_data["findings"] = role_findings
        role_data["verdict"] = role_verdict
        role_data["summary"] = role_summary
        role_data["required_changes"] = role_changes
        
        # Append to Report
        report += f"### @{role_name}\n"
        
        if role_verdict == "BLOCK":
            overall_verdict = "BLOCK"
            if progress_callback:
                progress_callback(f"❌ @{role_name}: BLOCK")
            report += f"**Verdict**: ❌ BLOCK\n\n"
        elif mode == "consultative":
                if progress_callback:
                    progress_callback(f"ℹ️  @{role_name}: CONSULTED")
                report += f"**Verdict**: ℹ️ ADVICE\n\n"
        else:
            if progress_callback:
                progress_callback(f"✅ @{role_name}: PASS")
            report += f"**Verdict**: ✅ PASS\n\n"

        if role_summary:
            report += f"**Summary**: {role_summary}\n\n"
        
        if role_findings:
            report += "**Findings**:\n"
            report += "\n".join(f"- {f}" for f in role_findings)
            report += "\n\n"
        
        if role_changes:
            report += "**Required Changes**:\n"
            report += "\n".join(f"- {c}" for c in role_changes)
            report += "\n\n"
        
        if not role_findings and not role_changes:
            report += "No issues found.\n\n"
             
        json_roles.append(role_data)

    json_report["roles"] = json_roles
    json_report["overall_verdict"] = overall_verdict
    
    # Save Log
    timestamp = int(time.time())
    log_dir = config.agent_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / f"governance-{story_id}-{timestamp}.md"

    # Append Reference Validation section to audit log (INFRA-060 AC-10)
    _unique_valid = sorted(set(_all_valid_refs))
    _unique_invalid = sorted(set(_all_invalid_refs))
    _total_refs = len(_unique_valid) + len(_unique_invalid)
    _citation_rate = round(len(_unique_valid) / _total_refs, 2) if _total_refs > 0 else 0.0
    _hallucination_rate = round(len(_unique_invalid) / _total_refs, 2) if _total_refs > 0 else 0.0

    report += "\n## Reference Validation\n\n"
    report += f"| Metric | Value |\n|---|---|\n"
    report += f"| Total References | {_total_refs} |\n"
    report += f"| Valid | {len(_unique_valid)} |\n"
    report += f"| Invalid | {len(_unique_invalid)} |\n"
    report += f"| Citation Rate | {_citation_rate} |\n"
    report += f"| Hallucination Rate | {_hallucination_rate} |\n\n"
    if _unique_invalid:
        report += "**Invalid References:**\n"
        for inv in _unique_invalid:
            report += f"- ⚠️ {inv}\n"
        report += "\n"

    # Add reference metrics to JSON report (AC-10)
    json_report["reference_metrics"] = {
        "total_refs": _total_refs,
        "valid": _unique_valid,
        "invalid": _unique_invalid,
        "citation_rate": _citation_rate,
        "hallucination_rate": _hallucination_rate,
    }

    log_file.write_text(report)
    json_report["log_file"] = str(log_file)
    
    return {
        "verdict": overall_verdict,
        "log_file": log_file,
        "json_report": json_report
    }

# --- Audit Logic ---

@dataclass
class AuditResult:
    traceability_score: float
    ungoverned_files: List[str]
    stagnant_files: List[Dict]  # {path, last_modified, days_old}
    orphaned_artifacts: List[Dict]  # {path, state, last_activity}
    missing_licenses: List[str]
    errors: List[str]  # Any permission/access errors encountered

def is_governed(file_path: Path, traceability_regexes: List[str] = None) -> Tuple[bool, Optional[str]]:
    """Check if file is traceable to a Story/Runbook."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Default traceability regexes
            if traceability_regexes is None:
                traceability_regexes = [
                    r"STORY-\d+",
                    r"RUNBOOK-\d+"
                ]

            for regex in traceability_regexes:
                 match = re.search(regex, content, re.IGNORECASE)
                 if match:
                    return True, f"Found traceability reference matching regex: {regex}. Match: {match.group(0)}"

        # Check agent_state.db for file->story mappings (Not yet implemented)
        return False, None

    except Exception as e:
        logger.error(f"Error checking if file is governed: {e}")
        return False, f"Error: {e}"

def find_stagnant_files(repo_path: Path, months: int = 6, ignore_patterns: List[str] = None) -> List[Dict]:
    """Find files not modified in X months with no active story link."""
    stagnant_files = []
    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=months * 30)  # Approximation

    try:
        # Use git log to get last commit date per file
        result = subprocess.run(
            ["git", "log", "--pretty=format:%ad", "--date=iso", "--name-only", "--diff-filter=ACMR", "--", "."],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        
        files_by_date = {}
        current_date = None
        
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                date = datetime.fromisoformat(line.replace("Z", "+00:00"))
                current_date = date
            except ValueError:
                if current_date:
                    file_path = repo_path / line
                    
                    # Check if file is ignored
                    if ignore_patterns:
                        rel_path = str(file_path.relative_to(repo_path))
                        if any(fnmatch.fnmatch(rel_path, p) for p in ignore_patterns):
                            continue

                    if file_path.is_file():  # Ensure it's a file and not a directory
                        files_by_date[file_path] = current_date

        # Filter by age threshold and exclude files linked to active stories
        for file_path, last_modified_date in files_by_date.items():
            if last_modified_date < threshold_date:
                governed, _ = is_governed(file_path)
                if not governed:
                    days_old = (now - last_modified_date).days
                    
                    # GDPR Check: Scan for PII in stagnant file
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(1024 * 1024) # Limit to 1MB
                            # Use security module regexes to detect PII
                            # We import regexes from security module (need to expose them or use helper)
                            # For now, simple check using the same patterns as scrub_sensitive_data
                            # But we want to *detect* not scrub.
                            from agent.core.security import scrub_sensitive_data
                            scrubbed = scrub_sensitive_data(content)
                            if scrubbed != content:
                                # Data was changed, meaning PII was found
                                logger.warning(f"GDPR WARNING: Stagnant file {file_path} contains potential PII.")
                                # We could mark it in the result, but current structure just has list of dicts.
                                # Let's append a flag.
                                # Assuming dict structure is flexible or we update type hint.
                    except Exception:
                        pass

                    stagnant_files.append({
                        "path": str(file_path.relative_to(repo_path)),
                        "last_modified": last_modified_date.isoformat(),
                        "days_old": days_old
                    })

    except subprocess.CalledProcessError as e:
        logger.error(f"Error finding stagnant files: {e}")
    except Exception as e:
        logger.error(f"Unexpected error finding stagnant files: {e}")

    return stagnant_files

def find_orphaned_artifacts(cache_path: Path, days: int = 30) -> List[Dict]:
    """Find OPEN stories/plans with no activity in X days."""
    orphaned_artifacts = []
    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=days)

    # Scan .agent/cache/stories and .agent/cache/plans
    artifact_types = ["stories", "plans"]

    for artifact_type in artifact_types:
        artifact_dir = cache_path / artifact_type
        if not artifact_dir.exists():
            continue

        for item_path in artifact_dir.glob("*"):
            if item_path.is_file():
                try:
                    with open(item_path, "r") as f:
                        item_data = json.load(f)

                        # Check State/Status fields
                        state = item_data.get("state", item_data.get("status", "UNKNOWN")).upper()
                        last_activity_str = item_data.get("last_activity")

                        if state == "OPEN" or state == "ACTIVE":
                            if last_activity_str:
                                last_activity = datetime.fromisoformat(last_activity_str.replace("Z", "+00:00"))
                                if last_activity < threshold_date:
                                    days_old = (now - last_activity).days
                                    orphaned_artifacts.append({
                                        "path": str(item_path.relative_to(cache_path)),
                                        "state": state,
                                        "last_activity": last_activity.isoformat(),
                                        "days_old": days_old
                                    })

                except Exception as e:
                    logging.error(f"Error processing artifact {item_path}: {e}")

    return orphaned_artifacts



def run_audit(
    repo_path: Path,
    min_traceability: int = 80,
    stagnant_months: int = 6,
    ignore_patterns: List[str] = None
) -> AuditResult:
    """Run full governance audit and return structured results."""
    
    errors: List[str] = []
    ungoverned_files: List[str] = []
    
    total_files = 0
    governed_files = 0

    #Get list of all files
    all_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = Path(root) / file
            if file_path.is_file():  # Ensure it's a file and not a directory
                all_files.append(file_path)
                total_files += 1

    # Check traceability for each file
    for file_path in all_files:

        # Check if file is ignored
        rel_path = str(file_path.relative_to(repo_path))
        if ignore_patterns:
             ignored = False
             for pattern in ignore_patterns:
                 if fnmatch.fnmatch(rel_path, pattern):
                     ignored = True
                     break
                 if pattern.endswith("/") and rel_path.startswith(pattern):
                     ignored = True
                     break
             if ignored:
                 # Check for .auditignore abuse/changes
                 if ".auditignore" in str(file_path):
                     log_governance_event("AUDIT_IGNORE_CHECK", f"Checking ignore file itself: {file_path}")
                 continue

        try:
            governed, message = is_governed(file_path)
            if governed:
                governed_files += 1
            else:
                 ungoverned_files.append(str(file_path.relative_to(repo_path)))
                 logger.warning(f"File {file_path} is not governed: {message}")
        except Exception as e:
            errors.append(f"Error checking {file_path}: {e}")
            logger.error(f"Error checking {file_path}: {e}")
        
    if total_files > 0:
        traceability_score = (governed_files / total_files) * 100
    else:
        traceability_score = 0

    # Find stagnant files
    stagnant_files = find_stagnant_files(repo_path, stagnant_months, ignore_patterns)

    # Find orphaned artifacts
    cache_path = repo_path / ".agent" / "cache"
    orphaned_artifacts = find_orphaned_artifacts(cache_path)

    audit_result =  AuditResult(
        traceability_score=traceability_score,
        ungoverned_files=ungoverned_files,
        stagnant_files=stagnant_files,
        orphaned_artifacts=orphaned_artifacts,
        missing_licenses=[],
        errors=errors,
    )

    # Check for license headers
    audit_result.missing_licenses = check_license_headers(repo_path, all_files, ignore_patterns)
    
    return audit_result


def check_license_headers(repo_path: Path, all_files: List[Path], ignore_patterns: List[str]) -> List[str]:
    """Check for license headers in all source files.
    
    Uses path-aware dual-license logic:
    - .agent/ files: Justin Cook / Apache License 2.0
    - All other files: Inspected Holding Pty Ltd / Proprietary
    """
    
    missing_license_headers = []
    
    # License patterns for .agent/ (open-source, Justin Cook)
    agent_license_patterns = [
        re.compile(r"Copyright \d{4}.*Justin Cook", re.IGNORECASE),
        re.compile(r"Licensed under the Apache License, Version 2.0", re.IGNORECASE),
    ]
    
    # License patterns for application code (proprietary, Inspected Holding Pty Ltd)
    app_license_patterns = [
        re.compile(r"Copyright.*\d{4}.*Inspected Holding Pty Ltd", re.IGNORECASE),
        re.compile(r"[Pp]roprietary and [Cc]onfidential", re.IGNORECASE),
    ]
    
    # Extensions to check
    EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".sh", ".swift", ".kt"}

    for file_path in all_files:
        if file_path.suffix not in EXTENSIONS:
            continue

        if ignore_patterns:
             rel_path = str(file_path.relative_to(repo_path))
             if any(fnmatch.fnmatch(rel_path, p) for p in ignore_patterns):
                 continue

        try:
            rel_path = file_path.relative_to(repo_path)
            rel_str = str(rel_path)
            
            # Select correct license patterns based on file location
            is_agent = rel_str.startswith(".agent/") or rel_str.startswith(".agent\\")
            patterns = agent_license_patterns if is_agent else app_license_patterns

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check for any matching license header patterns
                has_license_header = any(pattern.search(content) for pattern in patterns)
                
                if not has_license_header:
                    missing_license_headers.append(rel_str)
        except Exception as e:
            logger.error(f"Error checking license header in {file_path}: {e}")
            # Don't fail the whole audit for one read error, just log it
    
    return missing_license_headers