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
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        # file is in .agent/src/agent/core/config.py
        # .parents[4] resolves to the repo root (containing .agent)
        self.repo_root = Path(__file__).parents[4]
        
        self.agent_dir = self.repo_root / ".agent"
        self.src_dir = self.agent_dir / "src"
        self.templates_dir = self.agent_dir / "templates"
        self.etc_dir = self.agent_dir / "etc"
        self.rules_dir = self.agent_dir / "rules"
        self.instructions_dir = self.agent_dir / "instructions"
        self.cache_dir = self.agent_dir / "cache"
        self.adrs_dir = self.agent_dir / "adrs"
        self.logs_dir = self.agent_dir / "logs"
        self.backups_dir = self.agent_dir / "backups"

        self.stories_dir = self.cache_dir / "stories"
        self.plans_dir = self.cache_dir / "plans"
        self.runbooks_dir = self.cache_dir / "runbooks"
        
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load a YAML file safely."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML from {path}: {e}")
            raise

    def save_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        """Save YAML file atomically."""
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.error(f"Failed to save content to {path}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def backup_config(self, path: Path) -> Path:
        """Create a timestamped backup of a config file."""
        if not path.exists():
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}{path.suffix}"
        backup_path = self.backups_dir / backup_name
        
        shutil.copy2(path, backup_path)
        return backup_path

    def get_value(self, data: Dict[str, Any], dotted_key: str) -> Any:
        """Retrieve a value using dot-notation (e.g. 'models.gpt-4o.tier')."""
        keys = dotted_key.split(".")
        current = data
        for key in keys:
            # Handle list access via integer key
            if isinstance(current, list):
                if key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(current):
                        current = current[idx]
                        continue
                    else:
                         return None
                else:
                    return None
                    
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def set_value(self, data: Dict[str, Any], dotted_key: str, value: Any) -> None:
        """Set a value using dot-notation, creating nested dicts as needed."""
        keys = dotted_key.split(".")
        current = data
        for i, key in enumerate(keys[:-1]):
            # Handle list traversal or dict traversal
            if isinstance(current, list):
                if key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(current):
                        current = current[idx]
                        continue
                    else:
                        raise IndexError(f"List index out of range: {key}")
                else:
                     raise TypeError(f"Cannot access list with non-integer key: {key}")

            if key not in current or not isinstance(current[key], (dict, list)):
                # If next key implies a list item... 
                # This is tricky without schema. Default to dict.
                current[key] = {}
            current = current[key]
        
        # Set final value
        last_key = keys[-1]
        
        # Simple type inference for CLI inputs
        if isinstance(value, str):
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    pass
        
        if isinstance(current, list):
            if last_key.isdigit():
                idx = int(last_key)
                 # Extend list if needed? Or only support existing indices?
                 # Safe set: only existing
                if 0 <= idx < len(current):
                    current[idx] = value
                else:
                    raise IndexError(f"List index out of range: {last_key}")
            else:
                 raise TypeError(f"Cannot set list item with non-integer key: {last_key}")
        else:
            current[last_key] = value

    def get_council_tools(self, council_name: str) -> List[str]:
        """Retrieve allowed tools for a specific council."""
        # TODO: Load from agent.yaml or config file if present, otherwise default
        # For now, use the global default constants
        return DEFAULT_COUNCIL_TOOLS.get(council_name, DEFAULT_COUNCIL_TOOLS["default"])

        
config = Config()


def get_secret(key: str, service: Optional[str] = None) -> Optional[str]:
    """
    Get secret from secret manager or environment variable.
    
    Tries secret manager first (if initialized and unlocked), then falls back
    to environment variables. This provides backward compatibility.
    
    Args:
        key: Secret key name (e.g., 'api_key') or environment variable name
        service: Optional service name (e.g., 'openai', 'gemini')
        
    Returns:
        Secret value or None if not found
    """
    # Try secret manager first
    if service:
        try:
            from agent.core.secrets import get_secret_manager
            manager = get_secret_manager()
            if manager.is_initialized() and manager.is_unlocked():
                value = manager.get_secret(service, key)
                if value:
                    return value
        except Exception:
            pass  # Fall back to environment
    
    # Fallback to environment variable
    return os.getenv(key)


# Provider configuration
def get_provider_config(provider_name: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Retrieve the configuration for a given provider.
    
    Tries secret manager first, then falls back to environment variables.
    """
    provider = provider_name.lower()
    
    # Service to env var mapping
    env_map = {
        "gh": "GH_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    
    if provider not in env_map:
        return None
    
    # Try secret manager first, fall back to env var
    api_key = get_secret("api_key", provider) or os.getenv(env_map[provider])
    
    return {"api_key": api_key}


def get_valid_providers() -> List[str]:
    """
    Returns list of valid AI provider names.
    """
    return ["gh", "openai", "gemini", "anthropic"]


# Configuration for Agent Query feature (INFRA-017)
AGENT_VERSION = "1.0.0"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY")


def is_ai_configured() -> bool:
    """Checks if the necessary API keys for AI services are configured."""
    return bool(LLM_API_KEY)


# Default MCP Server Configurations
DEFAULT_MCP_SERVERS = {
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {}
    }
}

# Default Tools for Agent Councils
DEFAULT_COUNCIL_TOOLS = {
    "preflight": ["github:get_issue", "github:list_issues"],
    "panel": ["github:get_issue", "github:list_issues", "filesystem:read_file"],
    "default": []
}