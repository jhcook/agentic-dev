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
from pathlib import Path
from typing import Dict, Any

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

    async def load_context(self, story_id: str = "", legacy_context: bool = False) -> Dict[str, Any]:
        """
        Loads the full context: Global Rules, Agents, Agent Instructions, ADRs,
        and Source Code context.
        Returns a dictionary with formatted strings ready for LLM consumption.
        
        NOTE FOR CODE REVIEWERS: This is intentionally an async function because it performs
        asynchronous I/O via `await mcp_client.get_context(story_id)` when legacy_context is False.
        """
        from agent.core.context_source import load_source_tree, load_source_snippets

        source_tree = load_source_tree()
        source_code = load_source_snippets()
        logger.debug(
            "Source context: tree=%d chars, snippets=%d chars",
            len(source_tree), len(source_code),
        )

        if legacy_context:
            from agent.core.context_docs import load_adrs
            adrs = load_adrs()
            rules = self._load_global_rules()
            instructions = self._load_role_instructions()
        else:
            adrs = ""
            rules = ""
            instructions = ""

        # NotebookLM MCP / Local Vector DB integration
        context_str = ""
        if not legacy_context and story_id and not os.environ.get("AGENT_DISABLE_MCP"):
            try:
                from agent.core.mcp.client import MCPClient
                mcp_client = MCPClient()
                context_str = await mcp_client.get_context(story_id)
            except Exception as e:
                logger.debug(f"MCP Server not detected. Falling back to local Vector DB: {e}")
                context_str = self._query_local_vector_db(story_id)
        elif not legacy_context and story_id:
            context_str = self._query_local_vector_db(story_id)

        return {
            "rules": rules,
            "agents": self._load_agents(),
            "instructions": instructions,
            "adrs": adrs,
            "source_tree": source_tree,
            "source_code": source_code,
            "context": context_str,
        }

    def _query_local_vector_db(self, query: str) -> str:
        """
        Query local vector DB using ChromaDB or LanceDB.
        """
        try:
            from agent.db.journey_index import JourneyIndex
            db = JourneyIndex()
            return db.search(query)
        except Exception as e:
            logger.debug(f"Local JourneyIndex unavailable: {e}")
            return "Relevant context from local vector DB could not be retrieved."

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


    def _load_targeted_context(self, story_content: str) -> str:
        """Extracts file paths referenced in the story and returns their contents.

        Resolution priority:
        1. Precise paths from the Impact Analysis section (backtick-quoted, fully-prefixed).
           These are the most reliable — they were written by the engineer and contain the
           leading ``.agent/src/`` segment, so there is no ambiguity.
        2. Broad regex fallback for any ``path/with/slash.py`` pattern found elsewhere in
           the story text.  Bare filenames (no directory separator, e.g. ``__init__.py``)
           are *intentionally excluded* from the fallback to prevent ``rglob`` from
           resolving the wrong file (the classic ``__init__.py`` collision).
        """
        context = "TARGETED FILE CONTENTS:\n"
        seen: set = set()

        def _read_and_append(p: str, resolved: Path) -> None:
            """Read resolved path and append to context, with truncation guard."""
            if p in seen:
                return
            seen.add(p)
            if resolved.exists() and resolved.is_file():
                try:
                    raw = resolved.read_text(errors="ignore")
                    if len(raw) > 30000:
                        half = 14000
                        lines_omitted = (len(raw) - 2 * half) // 50
                        raw = raw[:half] + f"\n... ({lines_omitted} lines omitted) ...\n" + raw[-half:]
                    nonlocal context
                    context += f"\n--- TARGETED CONTEXT: {p} ---\n{raw}\n"
                except Exception:
                    pass
            else:
                context += f"\n--- TARGETED CONTEXT: {p} ---\n(FILE NOT FOUND)\n"

        # ── Pass 1: Precise Impact Analysis paths ────────────────────────────
        # Match any backtick-quoted path that contains at least one slash and
        # ends with a known extension. No prefix whitelist — the agent manages
        # the entire repo, and Impact Analysis sections can reference any file.
        # The slash requirement is the only invariant: it excludes bare names
        # like ``__init__.py`` while covering arbitrary repo layouts.
        ia_pattern = _re.compile(
            r"`([^`]+/[^`]+\.(?:py|md|yaml|yml|json|txt|sh))`"
        )
        for m in ia_pattern.finditer(story_content):
            p = m.group(1).strip()
            _read_and_append(p, config.repo_root / p)

        # ── Pass 2: Broad regex fallback — paths with at least one '/' ───────
        # Bare names (like ``__init__.py``) are excluded; they are too ambiguous
        # for rglob and are captured only when they appear as part of a full path
        # in Pass 1.
        broad_pattern = _re.compile(r"[\w\.\-]+(?:/[\w\.\-]+)+\.(?:py|md|yaml|yml|json|txt|sh)")
        for m in broad_pattern.finditer(story_content):
            p = m.group(0)
            if p in seen:
                continue
            file_path = config.repo_root / p
            _read_and_append(p, file_path)

        return context

    def _load_test_impact(self, story_content: str) -> str:
        """Extracts and formats test impact files from the story."""
        tests_dir = config.agent_dir / "tests"
        if not tests_dir.exists():
            return "No tests directory found."
        
        impact = "TEST IMPACT MATRIX:\n"
        # Extract files mentioned in the story
        paths = set(_re.findall(r"[\w\.\-/]+\.(?:py|md|yaml|yml|json|txt|sh)", story_content))
        for p in paths:
            module_path = p.replace("/", ".").replace(".py", "")
            for test_file in tests_dir.rglob("test_*.py"):
                try:
                    content = test_file.read_text(errors="ignore")
                    if module_path in content or test_file.name.replace("test_", "") in p:
                        impact += f"\n--- IMPACTED TEST: {test_file.name} ---\n"
                        # extract patch lines
                        for line in content.splitlines():
                            if module_path in line and ("patch" in line or "import" in line):
                                impact += f"{line.strip()}\n"
                except Exception:
                    pass
        return impact

    def _load_behavioral_contracts(self, story_content: str) -> str:
        """Extracts and formats behavioral contract context."""
        tests_dir = config.agent_dir / "tests"
        if not tests_dir.exists():
            return ""

        contracts = "BEHAVIORAL CONTRACTS:\n"
        paths = set(_re.findall(r"[\w\.\-/]+\.(?:py|md|yaml|yml|json|txt|sh)", story_content))
        for p in paths:
            for test_file in tests_dir.rglob("test_*.py"):
                if test_file.name.replace("test_", "") in p:
                    try:
                        content = test_file.read_text(errors="ignore")
                        for line in content.splitlines():
                            if "assert " in line or "=" in line and ("(" in line or "," in line):
                                contracts += f"{line.strip()}\n"
                    except Exception:
                        pass
        return contracts

context_loader = ContextLoader()
