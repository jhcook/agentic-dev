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
from agent.core.secrets import get_secret
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)

from typing import Optional, Callable

def extract_uuid(text: str) -> str:
    """Extracts a UUID from a string."""
    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text, re.IGNORECASE)
    if match:
        return match.group(0)
    return ""

async def _sync_notebook(progress_callback: Optional[Callable[[str], None]] = None) -> str:
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
        
        with tracer.start_as_current_span("notebooklm.sync.prepare_auth"):
            # Inject NOTEBOOKLM_COOKIES if present
            notebooklm_cookies = get_secret("cookies", "notebooklm")
            if notebooklm_cookies:
                logger.info("NotebookLM cookies found and injected for sync", extra={"method": "cookies"})
                if "env" not in mcp_config:
                    mcp_config["env"] = {}
                mcp_config["env"]["NOTEBOOKLM_COOKIES"] = notebooklm_cookies

        client = MCPClient(
            command=mcp_config["command"], 
            args=mcp_config.get("args", []), 
            env=mcp_config.get("env", {})
        )

        from agent.db.client import get_all_artifacts_content, upsert_artifact
        state_docs = get_all_artifacts_content("notebooklm_state")
        state = {}
        if state_docs and state_docs[0].get("content"):
            try:
                state = json.loads(state_docs[0]["content"])
            except Exception:
                pass

        notebook_id = state.get("notebook_id")

        try:
            async with client.session() as mcp_session:
                if not notebook_id:
                    logger.info("Creating a new NotebookLM notebook for agentic-dev...")
                    try:
                        result = await client.call_tool("notebook_create", {"title": f"agentic-dev ({config.repo_root.name})"}, session=mcp_session)
                        result_text = "\n".join([c.text for c in result.content if hasattr(c, "text")])
                        notebook_id = extract_uuid(result_text)
                        
                        if not notebook_id:
                            if "Unknown tool" in result_text:
                                logger.warning("NotebookLM tool not found (often due to missing authentication).")
                                logger.warning("Please run: agent mcp auth notebooklm")
                            else:
                                logger.error(f"Failed to extract notebook ID from response: {result_text}")
                            return "FAILED"
                    except Exception as e:
                        logger.warning(f"NotebookLM tool call failed (often due to missing authentication). Please run: `agent mcp auth notebooklm`")
                        logger.debug(f"Details: {e}")
                        return "FAILED"
                        
                    state["notebook_id"] = notebook_id
                    upsert_artifact(id="notebooklm_state", type="state", content=json.dumps(state), author="system")
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
                            
                        if progress_callback:
                            progress_callback(f"Syncing {file_key}...")
                            
                        logger.info(f"Syncing {file_key} to NotebookLM...")
                        content = file_path.read_text(errors="ignore")
                        scrubbed_content = scrub_sensitive_data(content)
                        
                        # Use the native tool name for NotebookLM
                        await client.call_tool("notebook_add_text", {
                            "notebook_id": notebook_id,
                            "title": file_key,
                            "text": scrubbed_content
                        }, session=mcp_session)
                        
                        synced_files[file_key] = mtime
                        state["synced_files"] = synced_files
                    except Exception as e:
                        logger.error(f"Failed to sync file {file_path}: {e}")

                upsert_artifact(id="notebooklm_state", type="state", content=json.dumps(state), author="system")
                logger.info("NotebookLM sync completed.")
            return "SUCCESS"
            
        except BaseException as e:
            logger.warning(f"NotebookLM sync failed or degraded: {e}")
            return "FAILED"

async def ensure_notebooklm_sync(progress_callback: Optional[Callable[[str], None]] = None) -> str:
    """Synchronize local ADRs and MDC rules to NotebookLM. Returns status string."""
    return await _sync_notebook(progress_callback)

async def flush_notebooklm() -> bool:
    """Delete the NotebookLM notebook via MCP and clear local state."""
    from opentelemetry import trace
    from agent.db.client import get_all_artifacts_content, delete_artifact
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("notebooklm.flush"):
        try:
            user_config = config.load_yaml(config.etc_dir / "agent.yaml")
        except FileNotFoundError:
            user_config = {}
            
        servers = config.get_value(user_config, "agent.mcp.servers") or {}
    
        if "notebooklm" not in servers:
            logger.debug("NotebookLM MCP server not configured. Cannot flush.")
            return False

        mcp_config = servers["notebooklm"]
        
        # Inject NOTEBOOKLM_COOKIES if present
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

        state_docs = get_all_artifacts_content("notebooklm_state")
        state = {}
        if state_docs and state_docs[0].get("content"):
            try:
                state = json.loads(state_docs[0]["content"])
            except Exception:
                pass

        notebook_id = state.get("notebook_id")
        
        success = False
        try:
            if notebook_id:
                logger.info(f"Deleting NotebookLM notebook via MCP: {notebook_id}...")
                async with client.session() as mcp_session:
                    try:
                        result = await client.call_tool("notebook_delete", {"notebook_id": notebook_id, "confirm": True}, session=mcp_session)
                        result_text = "\\n".join([c.text for c in result.content if hasattr(c, "text")])
                        logger.info(f"Notebook deleted: {result_text.strip()}")
                        success = True
                    except Exception as e:
                        logger.error(f"Failed to delete notebook {notebook_id}: {e}")
            else:
                logger.info("No active NotebookLM notebook found in local state to delete.")
                success = True
                
            # Always delete the local state if flush was requested
            delete_success = delete_artifact("notebooklm_state", "state")
            if delete_success:
                logger.info("Successfully reset local NotebookLM sync state.")
            
            return success
        except BaseException as e:
            logger.warning(f"NotebookLM flush failed: {e}")
            return False
