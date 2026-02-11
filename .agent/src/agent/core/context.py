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

import yaml

from agent.core.config import config
from agent.core.utils import scrub_sensitive_data


class ContextLoader:
    def __init__(self):
        self.rules_dir = config.rules_dir
        self.agents_path = config.etc_dir / "agents.yaml"
        self.instructions_dir = config.instructions_dir
        self.adrs_dir = config.agent_dir / "adrs"

    def load_context(self) -> dict:
        """
        Loads the full context: Global Rules, Agents, Agent Instructions, and ADRs.
        Returns a dictionary with formatted strings ready for LLM consumption.
        """
        return {
            "rules": self._load_global_rules(),
            "agents": self._load_agents(),
            "instructions": self._load_role_instructions(),
            "adrs": self._load_adrs()
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

                # Extract decision section (first paragraph only for brevity)
                decision = ""
                decision_match = re.search(
                    r"^##\s+Decision\s*\n+(.*?)(?=\n##|\n###|\Z)",
                    content,
                    re.MULTILINE | re.DOTALL | re.IGNORECASE,
                )
                if decision_match:
                    # Take first paragraph (up to double newline)
                    raw = decision_match.group(1).strip()
                    first_para = raw.split("\n\n")[0].strip()
                    decision = first_para

                context += f"- **{title}** [{state}]: {decision}\n"

        if not has_adrs:
            context += "(No ADRs found)\n"

        return scrub_sensitive_data(context)


context_loader = ContextLoader()
