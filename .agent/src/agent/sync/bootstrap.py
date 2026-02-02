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

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import typer
from rich.prompt import Confirm, Prompt

from agent.core.config import config
from agent.core.notion.client import NotionClient
from agent.core.secrets import get_secret

logger = logging.getLogger(__name__)

SCHEMA_FILE = config.agent_dir / "etc" / "notion_schema.json"
STATE_FILE = config.cache_dir / "notion_state.json"

class NotionBootstrap:
    def __init__(self, token: str = None, parent_page_id: str = None):
        self.token = token or get_secret("notion_token", service="agent")
        if not self.token:
             from os import getenv
             self.token = getenv("NOTION_TOKEN")
             
        if not self.token:
            logger.error("Notion Token not found.")
            raise typer.Exit(code=1)

        self.client = NotionClient(self.token)
        self.parent_page_id = parent_page_id or get_secret("notion_parent_page_id", service="agent")
        if not self.parent_page_id:
             from os import getenv
             self.parent_page_id = getenv("NOTION_PARENT_PAGE_ID")

    def run(self):
        """Main execution flow for bootstrapping."""
        if not self.parent_page_id:
            logger.warning("NOTION_PARENT_PAGE_ID is missing.")
            self.parent_page_id = Prompt.ask("Enter the Notion Page ID to create databases in")
            if not self.parent_page_id:
                logger.error("Parent Page ID required.")
                return

        logger.info(f"Bootstrapping Notion Environment in Page: {self.parent_page_id}")
        
        # Load Schema
        if not SCHEMA_FILE.exists():
            logger.error(f"Schema file not found: {SCHEMA_FILE}")
            return
        
        with open(SCHEMA_FILE, "r") as f:
            schema = json.load(f)

        state = self._load_state()
        
        # Pass 1: Create Databases
        for db_key, db_def in schema.get("databases", {}).items():
            if db_key not in state:
                logger.info(f"Creating {db_def['title']}...")
                new_id = self._create_database(db_key, db_def)
                if new_id:
                    state[db_key] = new_id
        
        self._save_state(state)
        
        # Pass 2: Relations
        logger.info("Linking relations...")
        for db_key, db_def in schema.get("databases", {}).items():
            self._update_relations(db_key, db_def, state)
            
        # Pass 3: Templates
        # TODO: Port template logic if needed, skipping for now to focus on core structure
        
        logger.info("Bootstrap complete.")

    def _load_state(self) -> Dict[str, str]:
        if not STATE_FILE.exists():
            return {}
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, state: Dict[str, str]):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _create_database(self, db_key: str, db_def: Dict[str, Any]) -> Optional[str]:
        # Minimal creation (Title only first, or full properties sans relations)
        props = {}
        for p_name, p_def in db_def.get("properties", {}).items():
            t_prop = self._transform_property(p_name, p_def, is_creation=True)
            if t_prop:
                props[p_name] = t_prop
                
        payload = {
            "parent": {"page_id": self.parent_page_id},
            "title": [{"type": "text", "text": {"content": db_def["title"]}}],
            "properties": props
        }
        
        try:
            res = self.client._request("POST", "databases", payload)
            return res.get("id")
        except Exception as e:
            logger.error(f"Failed to create {db_key}: {e}")
            return None

    def _update_relations(self, db_key: str, db_def: Dict[str, Any], state: Dict[str, str]):
        db_id = state.get(db_key)
        if not db_id: return

        props = {}
        for p_name, p_def in db_def.get("properties", {}).items():
            if p_def["type"] == "relation":
                 target_key = p_def.get("relation_target")
                 target_id = state.get(target_key)
                 if target_id:
                     props[p_name] = {"relation": {"database_id": target_id, "type": "dual_property", "dual_property": {}}}

        if props:
            try:
                self.client.update_page_properties(db_id, props) # Actually DB update uses same endpoint structure? No, PATCH databases/:id
                # Only properties allowed in update
                self.client._request("PATCH", f"databases/{db_id}", {"properties": props})
            except Exception as e:
                logger.error(f"Failed to update relations for {db_key}: {e}")

    def _transform_property(self, name: str, prop_def: Dict[str, Any], is_creation: bool) -> Optional[Dict[str, Any]]:
        p_type = prop_def["type"]
        if p_type == "title": return {"title": {}}
        elif p_type == "rich_text": return {"rich_text": {}}
        elif p_type == "select": 
            opts = [{"name": o["name"], "color": o.get("color", "default")} for o in prop_def.get("options", [])]
            return {"select": {"options": opts}}
        elif p_type == "multi_select":
            opts = [{"name": o["name"], "color": o.get("color", "default")} for o in prop_def.get("options", [])]
            return {"multi_select": {"options": opts}}
        elif p_type == "date": return {"date": {}}
        elif p_type == "checkbox": return {"checkbox": {}}
        elif p_type == "number": return {"number": {"format": prop_def.get("format", "number")}}
        return None
