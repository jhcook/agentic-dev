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

# Licensed under the Apache License, Version 2.0 (the "License");
from agent.core.logger import get_logger
from agent.core.check.models import SyncOraclePatternResult
from opentelemetry import trace

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

def sync_oracle_pattern() -> SyncOraclePatternResult:
    """Implement NotebookLM / Notion Sync.
    
    Synchronizes local context with external Oracle sources (Notion, NotebookLM).
    If an external source cannot be reached, falls back to a purely local 
    Vector DB (ChromaDB) ensuring offline mode degrades gracefully.
    
    Returns:
        SyncOraclePatternResult indicating the status of each system.
    """
    with tracer.start_as_current_span("sync_oracle_pattern"):
        result: SyncOraclePatternResult = {
            "notebooklm_ready": False,
        "notebooklm_status": "UNKNOWN",
        "notion_ready": False,
        "notion_status": "UNKNOWN",
        "vector_db_ready": False,
        "vector_db_status": "UNKNOWN"
    }

    try:
        from agent.sync.notion import NotionSync
        NotionSync()
        result["notion_ready"] = True
        result["notion_status"] = "Notion sync ready (Oracle Pattern context active)."
    except Exception as e:
        logger.warning("Notion sync unreachable", extra={"error": str(e)})
        result["notion_status"] = f"Notion sync unreachable: {e}. Oracle Pattern may have stale context."

    try:
        import asyncio
        from agent.sync.notebooklm import ensure_notebooklm_sync
        
        sync_status = asyncio.run(ensure_notebooklm_sync(progress_callback=None))
            
        if sync_status == "SUCCESS":
            result["notebooklm_ready"] = True
            result["notebooklm_status"] = "NotebookLM sync ready."
        elif sync_status == "NOT_CONFIGURED":
            result["notebooklm_status"] = "NotebookLM sync not configured."
        else:
            result["notebooklm_status"] = "NotebookLM sync unavailable or degraded."
    except Exception as e:
        logger.warning("NotebookLM sync unreachable", extra={"error": str(e)})
        result["notebooklm_status"] = f"NotebookLM sync unreachable: {e}."

    if not result["notebooklm_ready"]:
        try:
            from agent.db.journey_index import JourneyIndex
            idx = JourneyIndex()
            idx.build()
            result["vector_db_ready"] = True
            result["vector_db_status"] = "Local Vector DB ready."
        except Exception as e:
            logger.error("Local Vector DB build failed", extra={"error": str(e)})
            result["vector_db_status"] = f"Local Vector DB build failed: {e}."

    return result