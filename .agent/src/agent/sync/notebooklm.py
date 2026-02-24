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

import asyncio
import json
import logging
import re
from pathlib import Path

from agent.core.config import config
from agent.core.mcp.client import MCPClient
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)

def extract_uuid(text: str) -> str:
    """Extracts a UUID from a string."""
    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text, re.IGNORECASE)
    if match:
        return match.group(0)
    return ""

async def _sync_notebook() -> str:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("notebooklm.sync"):
        try:
            user_config = config.load_yaml(config.etc_dir / "agent.yaml")
        except FileNotFoundError:
            user_config = {}
            
        servers = config.get_value(user_config, "agent.mcp.servers") or {}
    
        if "notebooklm" not in servers:
            logger.debug("NotebookLM MCP server not configured. Skipping sync.")
            return "NOT_CONFIGURED"

        mcp_config = servers["notebooklm"]
        client = MCPClient(
            command=mcp_config["command"], 
            args=mcp_config.get("args", []), 
            env=mcp_config.get("env", {})
        )

        state_file = config.agent_dir / "cache" / "notebooklm_state.json"
        state = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
            except Exception:
                pass

        notebook_id = state.get("notebook_id")

        try:
            if not notebook_id:
                logger.info("Creating a new NotebookLM notebook for agentic-dev...")
                try:
                    result = await client.call_tool("mcp_notebooklm_notebook_create", {"title": f"agentic-dev ({config.repo_root.name})"})
                    result_text = "\n".join([c.text for c in result.content if hasattr(c, "text")])
                    notebook_id = extract_uuid(result_text)
                    
                    if not notebook_id:
                        if "Unknown tool" in result_text:
                            logger.warning("NotebookLM tool not found (often due to missing authentication).")
                            logger.warning("Please run: uv tool run --from notebooklm-mcp-server notebooklm-mcp-auth")
                        else:
                            logger.error(f"Failed to extract notebook ID from response: {result_text}")
                        return "FAILED"
                except Exception as e:
                    logger.warning(f"NotebookLM tool call failed (often due to missing authentication). Please run: `uv tool run --from notebooklm-mcp-server notebooklm-mcp-auth`")
                    logger.debug(f"Details: {e}")
                    return "FAILED"
                    
                state["notebook_id"] = notebook_id
                state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(state_file, "w") as f:
                    json.dump(state, f)
                logger.info(f"Successfully created NotebookLM notebook: {notebook_id}")

            # Gather files to sync
            adrs_dir = config.repo_root / ".agent" / "adrs"
            rules_dir = config.repo_root / ".agent" / "rules"
            
            cache_dirs = [
                config.agent_dir / "cache" / "journeys",
                config.agent_dir / "cache" / "plans",
                config.agent_dir / "cache" / "runbooks",
                config.agent_dir / "cache" / "stories"
            ]
            
            files_to_sync = []
            if adrs_dir.exists():
                files_to_sync.extend(list(adrs_dir.rglob("*.md")))
            if rules_dir.exists():
                files_to_sync.extend(list(rules_dir.rglob("*.mdc")))
                
            for cdir in cache_dirs:
                if cdir.exists():
                    files_to_sync.extend(list(cdir.rglob("*.md")))
                    files_to_sync.extend(list(cdir.rglob("*.yaml")))
                    files_to_sync.extend(list(cdir.rglob("*.yml")))
                
            synced_files = state.get("synced_files", {})
            
            for file_path in files_to_sync:
                try:
                    mtime = file_path.stat().st_mtime
                    file_key = str(file_path.relative_to(config.repo_root))
                    
                    if file_key in synced_files and synced_files[file_key] >= mtime:
                        # Skip if not modified
                        continue
                        
                    logger.info(f"Syncing {file_key} to NotebookLM...")
                    content = file_path.read_text(errors="ignore")
                    scrubbed_content = scrub_sensitive_data(content)
                    
                    # Provide the expected mcp_notebooklm_ prefix for NotebookLM tools
                    await client.call_tool("mcp_notebooklm_notebook_add_text", {
                        "notebook_id": notebook_id,
                        "title": file_key,
                        "text": scrubbed_content
                    })
                    
                    synced_files[file_key] = mtime
                    with open(state_file, "w") as f:
                        state["synced_files"] = synced_files
                        json.dump(state, f)
                        
                except Exception as e:
                    logger.error(f"Failed to sync file {file_path}: {e}")

            logger.info("NotebookLM sync completed.")
            return "SUCCESS"
            
        except BaseException as e:
            logger.warning(f"NotebookLM sync failed or degraded: {e}")
            return "FAILED"

async def _delete_remote_notebook() -> bool:
    """Attempts to delete the current NotebookLM notebook using the stored ID."""
    try:
        user_config = config.load_yaml(config.etc_dir / "agent.yaml")
    except FileNotFoundError:
        user_config = {}
        
    servers = config.get_value(user_config, "agent.mcp.servers") or {}

    if "notebooklm" not in servers:
        logger.debug("NotebookLM MCP server not configured.")
        return False

    mcp_config = servers["notebooklm"]
    
    # Inject NOTEBOOKLM_COOKIES if present
    from agent.core.secrets import get_secret
    notebooklm_cookies = get_secret("cookies", "notebooklm")
    if notebooklm_cookies:
        if "env" not in mcp_config:
            mcp_config["env"] = {}
        mcp_config["env"]["NOTEBOOKLM_COOKIES"] = notebooklm_cookies
        
    client = MCPClient(
        command=mcp_config["command"], 
        args=mcp_config.get("args", []), 
        env=mcp_config.get("env", {})
    )

    state_file = config.agent_dir / "cache" / "notebooklm_state.json"
    if not state_file.exists():
        return False
        
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
        notebook_id = state.get("notebook_id")
        
        if notebook_id:
            logger.info(f"Attempting to delete remote NotebookLM notebook: {notebook_id}")
            result = await client.call_tool("mcp_notebooklm_notebook_delete", {
                "notebook_id": notebook_id,
                "confirm": True
            })
            logger.info("Remote NotebookLM notebook deleted successfully.")
            return True
    except Exception as e:
        logger.warning(f"Failed to delete remote NotebookLM notebook: {e}")
        
    return False

def delete_remote_notebook() -> bool:
    """Synchronous wrapper to delete the remote notebook."""
    return asyncio.run(_delete_remote_notebook())

def ensure_notebooklm_sync() -> str:
    """Synchronize local ADRs and MDC rules to NotebookLM. Returns status string."""
    return asyncio.run(_sync_notebook())
