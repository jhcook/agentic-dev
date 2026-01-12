
import yaml
from agent.core.config import config
from agent.core.utils import scrub_sensitive_data

class ContextLoader:
    def __init__(self):
        self.rules_dir = config.rules_dir
        self.agents_path = config.etc_dir / "agents.yaml"
        self.instructions_dir = config.instructions_dir

    def load_context(self) -> dict:
        """
        Loads the full context: Global Rules, Agents, and Agent Instructions.
        Returns a dictionary with formatted strings ready for LLM consumption.
        """
        return {
            "rules": self._load_global_rules(),
            "agents": self._load_agents(),
            "instructions": self._load_role_instructions()
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
                    for instr_file in role_instr_dir.glob("*.md"):
                        content = instr_file.read_text(errors="ignore")
                        instructions += f"\n--- INSTRUCTIONS FOR @{role.upper()} ({instr_file.name}) ---\n{content}\n"
            
            return scrub_sensitive_data(instructions)
        except Exception:
            return ""

context_loader = ContextLoader()
