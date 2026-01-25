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

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import re
from pathlib import Path
from backend.admin.logger import log_bus

router = APIRouter(prefix="/api/admin/governance", tags=["governance"])

# Resolve repo root absolute path
# .agent/src/backend/routers/governance.py -> repo_root
BASE_DIR = Path(__file__).resolve().parents[4]

CACHE_DIR = BASE_DIR / ".agent" / "cache"
RULES_DIR = BASE_DIR / ".agent" / "rules"
ADR_DIR = BASE_DIR / ".agent" / "adrs"

class Artifact(BaseModel):
    id: str         # Logical ID (WEB-005)
    uid: str        # Unique ID for Graph (WEB-005-story)
    type: str  # story, plan, runbook, adr
    title: str
    status: str
    path: str
    content: Optional[str] = None
    links: List[str] = []

class EstateGraph(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class ArtifactUpdate(BaseModel):
    content: str

def parse_markdown_links(content: str) -> List[str]:
    """Find [ID] or [Link](...) references to other artifacts."""
    links = []
    # Match [WEB-005]
    story_matches = re.findall(r'\[([A-Z]+-\d+)\]', content)
    links.extend(story_matches)
    # Match ADR-XXX
    adr_matches = re.findall(r'(ADR-\d+)', content)
    links.extend(adr_matches)
    return list(set(links))

def scan_artifacts() -> List[Artifact]:
    artifacts = []
    
    # helper to process file
    def process_file(path: Path, art_type: str):
        if not path.exists(): return
        try:
            content = path.read_text(encoding='utf-8')
            
            # Extract title (first line # Title)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else path.name
            
            # Extract status
            status_match = re.search(r'^##\s+State\s*\n\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
            # Fallback for old syntax "Status: OPEN"
            if not status_match:
                 status_match = re.search(r'^Status:\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
            
            status = status_match.group(1).upper() if status_match else "UNKNOWN"
            
            # Extract ID from filename (WEB-005-...)
            id_match = re.match(r'([A-Z]+-\d+|ADR-\d+)', path.name)
            art_id = id_match.group(1) if id_match else path.stem
            
            # Generate Unique ID for Graph/ReactFlow
            # e.g. WEB-005-story
            uid = f"{art_id}-{art_type}"
            
            links = parse_markdown_links(content)
            
            artifacts.append(Artifact(
                id=art_id,
                uid=uid,
                type=art_type,
                title=title,
                status=status,
                path=str(path),
                links=links
            ))
        except Exception as e:
            log_bus.broadcast("error", f"Failed to process file {path}: {e}")

    # Stories
    for f in (CACHE_DIR / "stories").rglob("*.md"): process_file(f, "story")
    # Plans
    for f in (CACHE_DIR / "plans").rglob("*.md"): process_file(f, "plan")
    # Runbooks
    for f in (CACHE_DIR / "runbooks").rglob("*.md"): process_file(f, "runbook")
    # ADRs
    if ADR_DIR.exists():
        for f in ADR_DIR.rglob("*.md"): process_file(f, "adr")
        
    # Post-process: Implicit Links & Validating Links to UIDs
    # We need to map logical connections (Story WEB-005 -> Plan WEB-005)
    # And Explicit links (Text "WEB-005") -> Target UID
    
    # 1. Map Logical ID to List of UIDs
    # e.g. "WEB-005" -> ["WEB-005-story", "WEB-005-runbook"]
    logical_map = {}
    for art in artifacts:
        if art.id not in logical_map:
            logical_map[art.id] = []
        logical_map[art.id].append(art)
        
    # 2. Logic: Implicit Link (Runbook <-> Story)
    for art in artifacts:
        if art.type == 'runbook':
            # Find matching story
            siblings = logical_map.get(art.id, [])
            for sib in siblings:
                if sib.type == 'story':
                    # Add implicit link
                    if sib.id not in art.links:
                        art.links.append(sib.id) # Link purely by Logical ID for now
    
    return artifacts

@router.get("/artifacts", response_model=List[Artifact])
async def list_artifacts():
    try:
        return scan_artifacts()
    except Exception as e:
        log_bus.broadcast("error", f"List artifacts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph", response_model=EstateGraph)
async def get_estate_graph():
    try:
        artifacts = scan_artifacts()
        nodes = []
        edges = []
        
        # logical_id -> [uid, uid...]
        lookup = {}
        for art in artifacts:
            if art.id not in lookup: lookup[art.id] = []
            lookup[art.id].append(art)
            
        for art in artifacts:
            nodes.append({
                "id": art.uid, # Use Unique ID for Node
                "type": "custom",
                "data": { 
                    "label": art.id, 
                    "title": art.title,
                    "type": art.type,
                    "status": art.status,
                    "logical_id": art.id
                },
                "position": { "x": 0, "y": 0 }
            })
            
        edge_set = set() # Avoid duplicates
        
        for art in artifacts:
            for link_id in art.links:
                # link_id is usually a Logical ID (e.g. "WEB-005")
                # We need to find the target UID.
                targets = lookup.get(link_id, [])
                
                for target in targets:
                    # Avoid self-loops
                    if target.uid == art.uid: continue
                    
                    # Create edge: Sender UID -> Target UID
                    edge_id = f"{art.uid}->{target.uid}"
                    if edge_id in edge_set: continue
                    
                    edges.append({
                        "id": edge_id,
                        "source": art.uid,
                        "target": target.uid,
                        "type": "smoothstep"
                    })
                    edge_set.add(edge_id)
                    
        return EstateGraph(nodes=nodes, edges=edges)
    except Exception as e:
        log_bus.broadcast("error", f"Graph generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/artifact/{art_id}")
async def get_artifact_content(art_id: str):
    try:
        artifacts = scan_artifacts()
        target = next((a for a in artifacts if a.id == art_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Artifact not found")
            
        path = Path(target.path)
        if not path.is_relative_to(Path(".")): # Simple check, better would be resolved check
             raise HTTPException(status_code=403, detail="Access denied")
             
        return {"content": path.read_text(encoding='utf-8')}
    except HTTPException:
        raise
    except Exception as e:
        log_bus.broadcast("error", f"Read artifact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/artifact/{art_id}")
async def update_artifact(art_id: str, update: ArtifactUpdate):
    try:
        artifacts = scan_artifacts()
        target = next((a for a in artifacts if a.id == art_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Artifact not found")
            
        path = Path(target.path)
        
        # Atomic Write
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(update.content, encoding='utf-8')
        os.replace(tmp_path, path)
        
        log_bus.broadcast("info", f"Updated artifact {art_id}")
        return {"status": "success"}
    except Exception as e:
        log_bus.broadcast("error", f"Update artifact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class StatusUpdate(BaseModel):
    status: str

@router.patch("/artifact/{art_id}/status")
async def update_artifact_status(art_id: str, update: StatusUpdate):
    try:
        artifacts = scan_artifacts()
        target = next((a for a in artifacts if a.id == art_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Artifact not found")
            
        path = Path(target.path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
            
        content = path.read_text(encoding='utf-8')
        new_status = update.status.upper()
        
        # Regex to find ## State <status> or Status: <status>
        # We try both common patterns.
        
        # Pattern 1: ## State\nOPEN
        state_pattern = r'(^##\s+State\s*\n\s*)(\w+)'
        
        if re.search(state_pattern, content, re.MULTILINE | re.IGNORECASE):
            new_content = re.sub(state_pattern, f"\\g<1>{new_status}", content, count=1, flags=re.MULTILINE | re.IGNORECASE)
        else:
            # Pattern 2: Status: OPEN (YAML frontmatter style or list)
            status_pattern = r'(^Status:\s*)(\w+)'
            if re.search(status_pattern, content, re.MULTILINE | re.IGNORECASE):
                new_content = re.sub(status_pattern, f"\\g<1>{new_status}", content, count=1, flags=re.MULTILINE | re.IGNORECASE)
            else:
                # Fallback: Append to end if not found
                # Add standard "## State" header
                new_content = content + f"\n\n## State\n{new_status}\n"
        
        # Atomic Write
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(new_content, encoding='utf-8')
        os.replace(tmp_path, path)
        
        log_bus.broadcast("info", f"Updated status of {art_id} to {new_status}")
        return {"status": "success", "new_status": new_status}
    except Exception as e:
        log_bus.broadcast("error", f"Update status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preflight")
async def run_preflight(background_tasks: BackgroundTasks):
    # This would simulate triggering the agent preflight command
    # and streaming output via WebSocket.
    # For now, we'll just log an event.
    log_bus.broadcast("info", "Preflight requested (Simulation)")
    return {"status": "started"}
