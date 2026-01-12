import sqlite3
import time
import re
from pathlib import Path
from typing import Optional, List, Set

def get_db_path() -> Path:
    # Assuming run from repo root
    return Path(".agent/cache/agent.db")

def get_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)

def extract_state(content: str) -> str:
    """Extracts state from markdown content."""
    # Look for "Status: OPEN" or "State: DRAFT"
    match = re.search(r'^(?:Status|State):\s*(\w+)', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "UNKNOWN"

def extract_related_stories(content: str) -> Set[str]:
    """Extracts related story IDs from Plan markdown."""
    # Look for "## Related Story" or "## Related Stories" section
    # Then capture subsequent lines that look like IDs (e.g. INFRA-004, STORY-123)
    # Stop at next header '##'
    stories = set()
    
    # Non-compiled regex for simplicity in this context
    # Find the section
    section_match = re.search(r'^##\s+Related Stor(?:y|ies)(.*?)(^##|\Z)', content, re.DOTALL | re.MULTILINE)
    if section_match:
        section_content = section_match.group(1)
        # Find all ID-like strings in this section
        # Assuming Format: PRE-123 or STORY-123
        ids = re.findall(r'\b[A-Z]+-\d+\b', section_content)
        for i in ids:
            stories.add(i)
            
    return stories

def extract_linked_adrs(content: str) -> Set[str]:
    """Extracts linked ADR IDs from Story markdown."""
    adrs = set()
    # Find section ## Linked ADRs
    section_match = re.search(r'^##\s+Linked ADRs(.*?)(^##|\Z)', content, re.DOTALL | re.MULTILINE)
    if section_match:
        section_content = section_match.group(1)
        # Format: ADR-001 or - ADR-001
        ids = re.findall(r'\bADR-\d+\b', section_content)
        for i in ids:
            adrs.add(i)
    return adrs

def upsert_artifact(id: str, type: str, content: str, author: str = "agent"):
    """Inserts or updates an artifact in the local cache and manages links."""
    try:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON") # Ensure FK consistency
        cursor = conn.cursor()
        
        # Check if exists (using composite key)
        cursor.execute("SELECT version FROM artifacts WHERE id = ? AND type = ?", (id, type))
        row = cursor.fetchone()
        version = 1
        if row:
            version = row[0] + 1
            
        state = extract_state(content)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Upsert Artifact
        cursor.execute("""
            INSERT OR REPLACE INTO artifacts (id, type, content, last_modified, version, state, author)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id, type, content, timestamp, version, state, author))
        
        # Log History
        change_id = f"{id}-{type}-v{version}-{int(time.time())}"
        cursor.execute("""
            INSERT INTO history (change_id, artifact_id, artifact_type, timestamp, author, description, delta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (change_id, id, type, timestamp, author, f"Updated to version {version}", ""))
        
        # Handle Links
        # 1. Clear existing links from this source (full refresh of links for this version)
        cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (id, type))
        
        # 2. Parse and Insert new links
        if type == "plan":
            # Link Plan -> Stories (contains)
            related_stories = extract_related_stories(content)
            for story_id in related_stories:
                # Note: Target story might not exist yet in DB, but we still record the link intent?
                # SQLite FK will fail if target doesn't exist.
                # However, for distributed sync, we might need to store links even if target is missing locally yet.
                # BUT, I put FK constraint in schema.
                # So we verify existence first, or insert a placeholder?
                # For now, let's only link if target exists to satisfy FK.
                # OR: Removing FK constraint might be better for async sync, but robustnes...
                # Let's check existence.
                cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'story'", (story_id,))
                if cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id, type, story_id, "story", "contains"))
                else:
                    # Placeholder insert so FK passes? Or skip?
                    # Skip for now to avoid pollution. User effectively has a broken link until Story is pulled.
                    print(f"Warning: Linked Story {story_id} not found in local cache. Link skipped.")
                    pass

        elif type == "story":
            # Link Story -> ADRs (related)
            linked_adrs = extract_linked_adrs(content)
            for adr_id in linked_adrs:
                 cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'adr'", (adr_id,))
                 if cursor.fetchone():
                     cursor.execute("""
                        INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id, type, adr_id, "adr", "related"))

        elif type == "runbook":
            # Link Runbook -> Story (implements)
            # Runbook ID usually == Story ID
            story_id = id
            cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'story'", (story_id,))
            if cursor.fetchone():
                 cursor.execute("""
                        INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id, type, story_id, "story", "implements"))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Warning: Failed to sync to local DB: {e}")
        import traceback
        traceback.print_exc()
        return False
