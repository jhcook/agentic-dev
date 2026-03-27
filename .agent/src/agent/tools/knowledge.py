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

"""
Knowledge domain tools for ADRs, journeys, and vector search.
"""

import logging
from pathlib import Path
from agent.utils.tool_security import validate_safe_path

logger = logging.getLogger(__name__)

def read_adr(adr_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads an Architecture Decision Record by numeric ID or full ID.
    """
    adr_dir = repo_root / ".agent" / "adrs"
    if not adr_dir.exists():
        return "ADR directory not found."
    
    # Handle '043' -> 'ADR-043'
    search_id = adr_id if adr_id.startswith("ADR-") else f"ADR-{adr_id.zfill(3)}"
    matches = list(adr_dir.glob(f"{search_id}*.md"))
    
    if not matches:
        return f"Error: ADR {adr_id} not found."
    
    return matches[0].read_text(encoding="utf-8")

def read_journey(journey_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads a user journey definition document.
    """
    path = repo_root / ".agent" / "journeys" / f"{journey_id}.md"
    if not path.exists():
        # Fallback to cache
        path = repo_root / ".agent" / "cache" / "journeys" / f"{journey_id}.md"
        
    try:
        safe_path = validate_safe_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Journey '{journey_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading journey: {str(e)}"

async def search_knowledge(query: str, **kwargs) -> str:
    """
    Searches project documentation using vector similarity via ChromaDB.
    """
    try:
        from agent.core.ai.rag import rag_service
        # AC-3: natural language query returning ranked results
        results = await rag_service.query(query, limit=5)
        if not results:
            return "No matching knowledge entries found in the vector index."
        
        output = ["Knowledge Search Results (ranked):"]
        for i, res in enumerate(results, 1):
            snippet = res.content[:200].replace("\n", " ")
            output.append(f"{i}. [{res.id}] (Score: {res.score:.2f})\n   {snippet}...")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return f"Error performing vector search: {str(e)}"
