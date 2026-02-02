#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup Path to import Agent Core

# Script is in .agent/scripts/
# Script is in .agent/scripts/
ROOT_DIR = Path(__file__).resolve().parents[2] # repo root
AGENT_DIR = ROOT_DIR / ".agent"
SRC_DIR = AGENT_DIR / "src"
sys.path.append(str(SRC_DIR))

from agent.core.mcp.client import MCPClient
from agent.core.config import config

# Logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("notion_schema_manager")

SCHEMA_FILE = AGENT_DIR / "etc" / "notion_schema.json"
STATE_FILE = AGENT_DIR / "cache" / "notion_state.json"

class NotionSchemaManager:
    def __init__(self):
        self.schema = self._load_schema()
        self.token = os.getenv("NOTION_TOKEN")
        self.page_id = os.getenv("NOTION_PARENT_PAGE_ID")
        
        if not self.token:
            logger.error("NOTION_TOKEN environment variable is not set.")
            sys.exit(1)
            
        if not self.page_id:
            logger.error("NOTION_PARENT_PAGE_ID environment variable is not set.")
            sys.exit(1)

        # Initialize MCP Client
        # We use strict stdio communication with the official server
        self.client = MCPClient(
            command="npx", 
            args=["-y", "@notionhq/notion-mcp-server"],
            env={"NOTION_KEY": self.token} # Server expects NOTION_KEY
        )

    def _load_schema(self) -> Dict[str, Any]:
        if not SCHEMA_FILE.exists():
            logger.error(f"Schema file not found at {SCHEMA_FILE}")
            sys.exit(1)
        with open(SCHEMA_FILE, "r") as f:
            return json.load(f)

    def _load_state(self) -> Dict[str, Any]:
        if not STATE_FILE.exists():
            return {}
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    def _save_state(self, state: Dict[str, Any]):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    async def run(self):
        logger.info("Starting Notion Schema Sync...")
        logger.info(f"Target Page ID: {self.page_id}")
        
        state = self._load_state()
        failure_occurred = False
        
        # Pass 1: Create/Verify Databases (Simple Properties Only)
        logger.info("--- Pass 1: Creating Databases ---")
        for db_key, db_def in self.schema.get("databases", {}).items():
            db_title = db_def["title"]
            existing_id = state.get(db_key)
            
            if existing_id:
                logger.info(f"Checking existing database: {db_title} ({existing_id})")
                await self._update_database_schema(db_key, db_def, state)
            else:
                logger.info(f"Creating database: {db_title}...")
                success = await self._create_database(db_key, db_def, state)
                if not success:
                    failure_occurred = True
        
        # Pass 2: Update Relations (Dependent Properties)
        logger.info("--- Pass 2: Linking Relations ---")
        if not failure_occurred:
            for db_key, db_def in self.schema.get("databases", {}).items():
                if "properties" in db_def:
                    await self._update_relations(db_key, db_def, state)

        # Pass 3: Template Population
        if not failure_occurred:
            await self._ensure_templates(state)

        self._save_state(state)

        
        if failure_occurred:
            logger.error("Schema Sync Failed. Some databases could not be created.")
            sys.exit(1)
            
        logger.info("Schema Sync Complete.")

    def _transform_property(self, name: str, prop_def: Dict[str, Any], state: Dict[str, Any], is_creation: bool) -> Optional[Dict[str, Any]]:
        """
        Transforms simplified schema to Notion API format.
        Returns None if property should be skipped (e.g. relations during creation).
        """
        p_type = prop_def["type"]
        
        # Helper to format options
        def transform_options(opts):
            return [{"name": o["name"], "color": o.get("color", "default")} for o in opts]

        if p_type == "title":
            return {"title": {}}
        elif p_type == "rich_text":
            return {"rich_text": {}}
        elif p_type == "date":
            return {"date": {}}
        elif p_type == "checkbox":
            return {"checkbox": {}}
        elif p_type == "number":
             # Default to number format if not spec
             fmt = prop_def.get("format", "number")
             return {"number": {"format": fmt}}
        elif p_type == "select":
            return {"select": {"options": transform_options(prop_def.get("options", []))}}
        elif p_type == "multi_select":
            return {"multi_select": {"options": transform_options(prop_def.get("options", []))}}
        elif p_type == "relation":
            if is_creation:
                return None # Skip relations in Pass 1
            
            target_key = prop_def.get("relation_target")
            target_id = state.get(target_key)
            if not target_id:
                logger.warning(f"Relation target '{target_key}' not found for property '{name}'. Skipping.")
                return None
            
            return {"relation": {"database_id": target_id, "type": "dual_property", "dual_property": {}}}
        
        return None

    async def _create_database(self, db_key: str, db_def: Dict[str, Any], state: Dict[str, Any]) -> bool:
        # Construct Create Args - Pass 1 (No Relations)
        raw_props = db_def.get("properties", {})
        api_props = {}
        
        for p_name, p_def in raw_props.items():
            t_prop = self._transform_property(p_name, p_def, state, is_creation=True)
            if t_prop:
                api_props[p_name] = t_prop
                
        try:
            # Fallback to direct API call because MCP tool 'API-create-a-data-source' 
            # points to /v1/data_sources (invalid/redirect loop) and has SSL issues.
            import urllib.request
            import urllib.error
            from agent.core.net_utils import check_ssl_error

            url = "https://api.notion.com/v1/databases"
            payload = {
                "parent": {"page_id": self.page_id},
                "title": [{"type": "text", "text": {"content": db_def["title"]}}],
                "properties": api_props
            }
            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            
            try:
                # Execute request with default strict SSL context
                with urllib.request.urlopen(req) as res:
                    if res.getcode() == 200:
                        resp_body = res.read().decode("utf-8")
                        data = json.loads(resp_body)
                        new_id = data.get("id")
                        if new_id:
                            state[db_key] = new_id
                            logger.info(f"Successfully created '{db_def['title']}' -> {new_id}")
                            return True
                    else:
                        logger.error(f"API Error {res.getcode()}: {res.read().decode('utf-8')}")

            except Exception as e:
                # Use standardized SSL error checking
                ssl_msg = check_ssl_error(e, url="api.notion.com")
                if ssl_msg:
                    logger.error(ssl_msg)
                    return False
                
                # Check for other URLErrors specifically if not SSL
                if isinstance(e, urllib.error.HTTPError):
                     error_body = e.read().decode('utf-8')
                     logger.error(f"HTTP Error {e.code}: {e.reason}")
                     logger.error(f"Response Body: {error_body}")
                     raise e
                
                # Otherwise let the outer loop handle generic exceptions
                raise e
            
            return False

        except Exception as e:
            # We already logged details for HTTPError above, but the re-raise catches here.
            # Avoid double error logging if it's already handled?
            # Or just let it log the summary.
            if not isinstance(e, urllib.error.HTTPError):
                 logger.error(f"Failed to create database '{db_def['title']}': {e}")
            # Only print verbose tracebacks if explicitly requested/debug
            if logger.isEnabledFor(logging.DEBUG):
                import traceback
                logger.debug(traceback.format_exc())
            
        return False


    async def _update_database_schema(self, db_key: str, db_def: Dict[str, Any], state: Dict[str, Any]):
        """Pass 1.5: Update existing database schema (e.g. adding new select options)."""
        db_id = state.get(db_key)
        if not db_id:
            return

        # We only update properties that can be safely updated (Title, Select, Multi-Select)
        # We avoid Relation updates here as they are handled in Pass 2
        
        raw_props = db_def.get("properties", {})
        update_props = {}
        
        for p_name, p_def in raw_props.items():
            p_type = p_def["type"]
            # Only target select/multi_select for option updates, or title renaming
            if p_type in ["select", "multi_select"]:
                t_prop = self._transform_property(p_name, p_def, state, is_creation=True)
                if t_prop:
                    update_props[p_name] = t_prop

        if not update_props:
            return

        logger.info(f"Updating schema for {db_def['title']}...")
        
        import urllib.request
        from agent.core.net_utils import check_ssl_error

        url = f"https://api.notion.com/v1/databases/{db_id}"
        payload = {
            "properties": update_props
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        
        try:
             with urllib.request.urlopen(req) as res:
                if res.getcode() == 200:
                    logger.info(f"Successfully updated schema for '{db_def['title']}'")
                else:
                    logger.error(f"Failed to update schema for '{db_def['title']}': {res.read().decode('utf-8')}")
        except Exception as e:
            ssl_msg = check_ssl_error(e, url="api.notion.com")
            if ssl_msg:
                logger.error(ssl_msg)
            elif isinstance(e, urllib.error.HTTPError):
                 logger.error(f"HTTP Error {e.code} updating schema: {e.read().decode('utf-8')}")
            else:
                 logger.error(f"Error updating schema: {e}")

    async def _update_relations(self, db_key: str, db_def: Dict[str, Any], state: Dict[str, Any]):
        """Pass 2: Update database with relation properties."""
        db_id = state.get(db_key)
        if not db_id:
            return

        raw_props = db_def.get("properties", {})
        relation_props = {}
        
        for p_name, p_def in raw_props.items():
            if p_def["type"] == "relation":
                 t_prop = self._transform_property(p_name, p_def, state, is_creation=False)
                 if t_prop:
                     relation_props[p_name] = t_prop
        
        if not relation_props:
            return

        logger.info(f"Linking relations for {db_def['title']}...")
        
        import urllib.request
        from agent.core.net_utils import check_ssl_error

        url = f"https://api.notion.com/v1/databases/{db_id}"
        payload = {
            "properties": relation_props
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        
        try:
             with urllib.request.urlopen(req) as res:
                if res.getcode() == 200:
                    logger.info(f"Successfully linked relations for '{db_def['title']}'")
                else:
                    logger.error(f"Failed to link relations for '{db_def['title']}': {res.read().decode('utf-8')}")
        except Exception as e:
            ssl_msg = check_ssl_error(e, url="api.notion.com")
            if ssl_msg:
                logger.error(ssl_msg)
            elif isinstance(e, urllib.error.HTTPError):
                 logger.error(f"HTTP Error {e.code} updating relations: {e.read().decode('utf-8')}")
            else:
                 logger.error(f"Error updating relations: {e}")

    async def _ensure_templates(self, state: Dict[str, Any]):
        """Pass 3: Create Master Template Rows."""
        
        TEMPLATES = {
            "Stories": {
                "title": "! TEMPLATE: Story",
                "blocks": [
                    {"heading_2": {"rich_text": [{"text": {"content": "Problem Statement"}}]}},
                    {"paragraph": {"rich_text": [{"text": {"content": "Describe the problem..."}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "User Story"}}]}},
                    {"paragraph": {"rich_text": [{"text": {"content": "**As a** [Role]\n**I want** [Feature]\n**So that** [Benefit]"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Acceptance Criteria"}}]}},
                    {"to_do": {"rich_text": [{"text": {"content": "Scenario 1"}}]}},
                    {"callout": {"rich_text": [{"text": {"content": "💡 Tip: Right-click this row in the database view and select 'Duplicate' to start a new Story."}}], "icon": {"emoji": "💡"}}}
                ]
            },
            "Plans": {
                "title": "! TEMPLATE: Plan",
                "blocks": [
                    {"heading_1": {"rich_text": [{"text": {"content": "Implementation Plan"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Goal"}}]}},
                    {"paragraph": {"rich_text": [{"text": {"content": "..."}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Proposed Changes"}}]}},
                    {"heading_3": {"rich_text": [{"text": {"content": "Component A"}}]}},
                    {"callout": {"rich_text": [{"text": {"content": "💡 Tip: Right-click this row in the database view and select 'Duplicate' to start a new Plan."}}], "icon": {"emoji": "💡"}}}
                ]
            },
            "ADRs": {
                "title": "! TEMPLATE: ADR",
                "blocks": [
                    {"heading_1": {"rich_text": [{"text": {"content": "Title"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Status"}}]}},
                    {"paragraph": {"rich_text": [{"text": {"content": "Proposed"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Context"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Decision"}}]}},
                    {"heading_2": {"rich_text": [{"text": {"content": "Consequences"}}]}},
                    {"callout": {"rich_text": [{"text": {"content": "💡 Tip: Right-click this row in the database view and select 'Duplicate' to start a new ADR."}}], "icon": {"emoji": "💡"}}}
                ]
            }
        }

        import urllib.request
        from agent.core.net_utils import check_ssl_error

        logger.info("--- Pass 3: Template Population ---")

        for db_name, tmpl in TEMPLATES.items():
            db_id = state.get(db_name)
            if not db_id:
                continue

            # 1. Check if template exists
            # We query the database for a page with this exact title
            query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
            query_payload = {
                "filter": {
                    "property": "Title", # Assumes 'Title' is the name of the title prop
                    "title": {
                        "equals": tmpl["title"]
                    }
                }
            }
            
            # Need to find the actual name of the Title property from schema
            # Our notion_schema.json uses "Title" as the key, but we should double check schema?
            # For simplicity, we assume "Title" based on our schema definition.
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            exists = False
            try:
                data = json.dumps(query_payload).encode("utf-8")
                req = urllib.request.Request(query_url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req) as res:
                    if res.getcode() == 200:
                        body = json.loads(res.read().decode("utf-8"))
                        if body.get("results"):
                            exists = True
                            logger.info(f"Template '{tmpl['title']}' already exists in {db_name}.")
            except Exception as e:
                logger.warning(f"Failed to query templates for {db_name}: {e}")
                continue
            
            if exists:
                continue

            # 2. Create Template Page
            logger.info(f"Creating template '{tmpl['title']}' in {db_name}...")
            create_url = "https://api.notion.com/v1/pages"
            create_payload = {
                "parent": {"database_id": db_id},
                "properties": {
                    "Title": { # Again assuming 'Title' property name Matches schema
                        "title": [{"text": {"content": tmpl["title"]}}]
                    }
                },
                "children": tmpl["blocks"]
            }
            
            try:
                data = json.dumps(create_payload).encode("utf-8")
                req = urllib.request.Request(create_url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req) as res:
                    if res.getcode() == 200:
                        logger.info(f"Successfully created template in {db_name}")
                    else:
                        logger.error(f"Failed to create template: {res.read().decode('utf-8')}")
            except Exception as e:
                ssl_msg = check_ssl_error(e, url="api.notion.com")
                if ssl_msg:
                    logger.error(ssl_msg)
                else:
                    logger.error(f"Error creating template: {e}")

if __name__ == "__main__":
    manager = NotionSchemaManager()
    asyncio.run(manager.run())
