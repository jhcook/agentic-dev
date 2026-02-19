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

import logging
import os
import re as _re

import yaml

from agent.core.config import config
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)


class ContextLoader:
    def __init__(self):
        self.rules_dir = config.rules_dir
        self.agents_path = config.etc_dir / "agents.yaml"
        self.instructions_dir = config.instructions_dir
        self.adrs_dir = config.agent_dir / "adrs"

    def load_context(self) -> dict:
        """
        Loads the full context: Global Rules, Agents, Agent Instructions, ADRs,
        and Source Code context.
        Returns a dictionary with formatted strings ready for LLM consumption.
        """
        source_tree = self._load_source_tree()
        source_code = self._load_source_snippets()
        logger.debug(
            "Source context: tree=%d chars, snippets=%d chars",
            len(source_tree), len(source_code),
        )
        return {
            "rules": self._load_global_rules(),
            "agents": self._load_agents(),
            "instructions": self._load_role_instructions(),
            "adrs": self._load_adrs(),
            "source_tree": source_tree,
            "source_code": source_code,
        }

    def _load_global_rules(self) -> str:
        """Loads all .mdc files from the rules directory."""
        context = "GOVERNANCE RULES:\n"
        has_rules = False
        if self.rules_dir.exists():
            for rule_file in sorted(self.rules_dir.glob("*.mdc")):
                has_rules = True
                context += f"\n--- RULE: {rule_file.name} ---\n"
                context += rule_file.read_text(errors="ignore")
        
        if not has_rules:
            context += "(No rules found)"
        
        return scrub_sensitive_data(context)

    def _load_agents(self) -> dict:
        """Loads agent definitions from agents.yaml."""
        if not self.agents_path.exists():
            return {"description": "No agents defined.", "checks": ""}

        try:
            agents_data = yaml.safe_load(self.agents_path.read_text())
            description = ""
            checks = ""
            
            for agent in agents_data.get("team", []):
                role = agent.get("role", "unknown")
                name = agent.get("name", role.capitalize())
                desc = agent.get("description", "")
                
                description += f"- @{role.capitalize()} ({name}): {desc}\n"
                
                role_checks = "\n".join([f"  - {c}" for c in agent.get("governance_checks", [])])
                checks += f"- **@{role.capitalize()}**:\n{role_checks}\n"
            
            return {"description": description, "checks": checks}
        except Exception as e:
            return {"description": f"Error loading agents: {e}", "checks": ""}

    def _load_role_instructions(self) -> str:
        """Loads detailed instructions for each role found in agents.yaml."""
        if not self.agents_path.exists():
            return ""

        instructions = "DETAILED ROLE INSTRUCTIONS:\n"
        try:
            agents_data = yaml.safe_load(self.agents_path.read_text())
            for agent in agents_data.get("team", []):
                role = agent.get("role", "unknown").lower()
                role_instr_dir = self.instructions_dir / role
                
                if role_instr_dir.exists():
                    # Load both .md and .mdc files (rules use .mdc convention)
                    for instr_file in sorted(role_instr_dir.glob("*.md*")):
                        if instr_file.suffix in (".md", ".mdc"):
                            content = instr_file.read_text(errors="ignore")
                            instructions += f"\n--- INSTRUCTIONS FOR @{role.upper()} ({instr_file.name}) ---\n{content}\n"
            
            return scrub_sensitive_data(instructions)
        except Exception:
            return ""

    def _load_adrs(self) -> str:
        """Loads compact summaries of all ADRs from the adrs directory.

        Each ADR is summarized as: Title + State + Decision (first paragraph only).
        This keeps the token budget lean while giving AI full architectural context.
        """
        import re

        context = "ARCHITECTURAL DECISION RECORDS (ADRs):\n"
        context += "ADRs have ULTIMATE PRIORITY over all rules and instructions. "
        context += "When an ADR conflicts with a rule, the ADR WINS. "
        context += "Code that follows an ADR is COMPLIANT and must NOT be flagged as a required change or cause a BLOCK. "
        context += "If a conflict exists, note it as an informational finding only.\n\n"
        has_adrs = False

        if self.adrs_dir.exists():
            for adr_file in sorted(self.adrs_dir.glob("*.md")):
                has_adrs = True
                content = adr_file.read_text(errors="ignore")

                # Extract title (first H1)
                title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else adr_file.stem

                # Extract state
                state_match = re.search(
                    r"^##\s+State\s*\n+\s*(\w+)",
                    content,
                    re.MULTILINE | re.IGNORECASE,
                )
                state = state_match.group(1).strip() if state_match else "UNKNOWN"

                # Extract Decision OR Justification
                # EXC records use "Justification", ADRs use "Decision"
                decision = ""
                # Try Decision first
                decision_match = re.search(
                    r"^##\s+Decision\s*\n+(.*?)(?=\n##|\n###|\Z)",
                    content,
                    re.MULTILINE | re.DOTALL | re.IGNORECASE,
                )
                # Fallback to Justification
                if not decision_match:
                    decision_match = re.search(
                        r"^##\s+Justification\s*\n+(.*?)(?=\n##|\n###|\Z)",
                        content,
                        re.MULTILINE | re.DOTALL | re.IGNORECASE,
                    )

                if decision_match:
                    # Take first paragraph (up to double newline)
                    raw = decision_match.group(1).strip()
                    first_para = raw.split("\n\n")[0].strip()
                    decision = first_para

                # Prefix based on type
                prefix = "[EXCEPTION]" if adr_file.name.startswith("EXC-") else "[ADR]"
                context += f"- **{prefix} {title}** [{state}]: {decision}\n"

        if not has_adrs:
            context += "(No ADRs found)\n"

        return scrub_sensitive_data(context)

    def _load_source_tree(self) -> str:
        """Loads a file tree of the source directory for codebase context.

        Excludes __pycache__, .pyc, .env files, and other non-essential items.
        Returns an indented tree string or empty string if src/ doesn't exist.
        """
        src_dir = config.agent_dir / "src"
        if not src_dir.exists() or not src_dir.is_dir():
            return ""

        exclude_dirs = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
        exclude_exts = {".pyc", ".pyo"}
        exclude_files = {".env", ".env.local", ".env.production"}

        tree = "SOURCE FILE TREE:\n"
        file_count = 0
        for dirpath, dirnames, filenames in os.walk(src_dir):
            # Filter excluded directories in-place (os.walk respects this)
            dirnames[:] = sorted(
                d for d in dirnames if d not in exclude_dirs
            )
            rel = os.path.relpath(dirpath, src_dir)
            level = 0 if rel == "." else rel.count(os.sep) + 1
            indent = "  " * level
            dirname = os.path.basename(dirpath)
            tree += f"{indent}{dirname}/\n"
            sub_indent = "  " * (level + 1)
            for fname in sorted(filenames):
                if (
                    not any(fname.endswith(ext) for ext in exclude_exts)
                    and fname not in exclude_files
                ):
                    tree += f"{sub_indent}{fname}\n"
                    file_count += 1

        logger.debug("Source tree: %d files found", file_count)
        return scrub_sensitive_data(tree)

    def _load_source_snippets(self, budget: int = 0) -> str:
        """Loads compact source outlines (imports + signatures) from Python files.

        Walks all .py files under src/, extracts import lines and
        class/def signatures (not bodies), and concatenates them until
        the character budget is exhausted.

        Args:
            budget: Maximum character count for combined snippets.
                    If 0 (default), reads from AGENT_SOURCE_CONTEXT_CHAR_LIMIT
                    env var, falling back to 8000.

        Returns:
            Formatted string of source outlines, or empty string if unavailable.
        """
        src_dir = config.agent_dir / "src"
        if not src_dir.exists():
            return ""

        if budget <= 0:
            budget = int(
                os.environ.get("AGENT_SOURCE_CONTEXT_CHAR_LIMIT", "8000")
            )

        exclude_dirs = {"__pycache__", ".pytest_cache", "tests"}
        # Match class/def/async def signatures, including indented and decorated
        sig_pattern = _re.compile(
            r"^[ \t]*((?:@\w+.*\n[ \t]*)*"
            r"(?:class|def|async\s+def)\s+\S+.*?):\s*$",
            _re.MULTILINE,
        )

        snippets = "SOURCE CODE OUTLINES:\n"
        remaining = budget - len(snippets)
        file_count = 0

        for py_file in sorted(src_dir.rglob("*.py")):
            # Skip excluded directories
            if any(part in exclude_dirs for part in py_file.parts):
                continue
            # Skip trivial __init__.py files
            if py_file.name == "__init__.py" and py_file.stat().st_size < 200:
                continue

            try:
                content = py_file.read_text(errors="ignore")
            except OSError:
                continue

            rel_path = py_file.relative_to(config.agent_dir)
            lines: list[str] = []

            # Imports (first 20 import lines max)
            import_lines = [
                line
                for line in content.splitlines()
                if line.startswith(("import ", "from "))
            ][:20]
            if import_lines:
                lines.extend(import_lines)

            # Class/function signatures (with optional decorators)
            for m in sig_pattern.finditer(content):
                lines.append(m.group(1))

            if not lines:
                continue

            block = f"\n--- {rel_path} ---\n" + "\n".join(lines) + "\n"

            if len(block) > remaining:
                truncated = block[: remaining - 20] + "\n[...truncated...]\n"
                snippets += truncated
                file_count += 1
                break
            snippets += block
            remaining -= len(block)
            file_count += 1

        logger.debug("Source snippets: %d files included", file_count)
        return scrub_sensitive_data(snippets)


context_loader = ContextLoader()
