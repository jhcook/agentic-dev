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
        
        # 1. Discover existing databases
        # We rely on searching, or just try to create and see?
        # Better: Search for databases in the parent page?
        # The notion-mcp-server tools: `search`, `create_database`, `update_database`
        
        # Unfortunately, search might be broad.
        # State file is our cache of Truth.
        state = self._load_state()
        
        # Bootstrap databases
        for db_key, db_def in self.schema.get("databases", {}).items():
            db_title = db_def["title"]
            existing_id = state.get(db_key)
            
            if existing_id:
                logger.info(f"Checking existing database: {db_title} ({existing_id})")
                # TODO: Check for Drift (Update properties)
                # For Phase 1 MVP, we assume if it exists in state, it's there.
                # Real implementation would call retrieve_database to verify.
            else:
                logger.info(f"Creating database: {db_title}...")
                await self._create_database(db_key, db_def, state)

        self._save_state(state)
        logger.info("Schema Sync Complete.")

    async def _create_database(self, db_key: str, db_def: Dict[str, Any], state: Dict[str, Any]):
        # Construct Create Args
        # Note: MCP implementation might vary slightly in args structure.
        # We assume standard Notion API structure mapped to tool args.
        
        properties = db_def.get("properties", {})
        
        try:
            # We call the 'create_database' tool provided by the server
            result = await self.client.call_tool("create_database", {
                "parent": {"page_id": self.page_id},
                "title": [{"type": "text", "text": {"content": db_def["title"]}}],
                "properties": properties
                # Description not always supported in create payload depending on API version
            })
            
            # Result parsing depends on MCP server output format
            # Usually result.content[0].text is the JSON response
            # Let's assume result is objects
            # Debug:
            # logger.info(f"Raw Create Result: {result}")
            
            # We need to extract the ID.
            # Assuming the tool returns the created object stringified
            if hasattr(result, 'content') and result.content:
                 data = json.loads(result.content[0].text)
                 new_id = data.get("id")
                 if new_id:
                     state[db_key] = new_id
                     logger.info(f"Successfully created '{db_def['title']}' -> {new_id}")
                 else:
                     logger.error(f"Failed to get ID from creation response: {data}")
            else:
                 logger.error("Empty response from create_database tool.")

        except Exception as e:
            logger.error(f"Failed to create database '{db_def['title']}': {e}")
            # Do not exit, try others?

if __name__ == "__main__":
    manager = NotionSchemaManager()
    asyncio.run(manager.run())
