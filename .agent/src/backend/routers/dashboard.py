from fastapi import APIRouter, HTTPException
from typing import List, Dict
from backend.routers.governance import scan_artifacts, Artifact
from typing import Any

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stories")
async def get_stories() -> List[Dict[str, Any]]:
    """Returns all stories."""
    try:
        artifacts = scan_artifacts()
        stories = [art.dict() for art in artifacts if art.type == 'story']
        # Sort by ID descending (newest first)
        stories.sort(key=lambda x: x['id'], reverse=True)
        return stories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats():
    """Returns project statistics."""
    try:
        artifacts = scan_artifacts()
        
        stories = [a for a in artifacts if a.type == 'story']
        adrs = [a for a in artifacts if a.type == 'adr']
        # PRs are not tracked in artifacts yet, returning mock or 0
        
        # Calculate Active Stories (Not CLOSED/COMMITTED? definition of active varies)
        # AC says: "Active Stories (Status != CLOSED)"
        # Let's count IN_PROGRESS, REVIEW, DRAFT? Or just not CLOSED.
        # usually COMMITTED is done? Runbook AC says "Active Work List (Table of IN_PROGRESS items)".
        # Let's stick to "Status != CLOSED" for the widget.
        
        active_count = sum(1 for s in stories if s.status.upper() != "CLOSED" and s.status.upper() != "DONE") 
        # Also maybe exclude COMMITTED if that equates to Done? 
        # The user's Kanban has COMMITTED column. Runbook says "Active Work List" is IN_PROGRESS.
        # Let's count IN_PROGRESS + REVIEW + DRAFT as "Active".
        
        active_stories = sum(1 for s in stories if s.status.upper() in ["IN_PROGRESS", "REVIEW", "DRAFT"])
        
        # Total ADRs
        total_adrs = len(adrs)
        
        pending_prs = 0 # No data source for this yet
        
        return {
            "activeStories": active_stories,
            "pendingPRs": pending_prs,
            "totalADRs": total_adrs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
