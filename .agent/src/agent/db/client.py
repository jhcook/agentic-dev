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

import re
import sqlite3
import time
from pathlib import Path
from typing import Optional, Set

from agent.core.utils import scrub_sensitive_data
from agent.db.init import init_db


def get_db_path() -> Path:
    """Returns the path to the local Agent SQLite database."""
    from agent.core.config import config
    return config.cache_dir / "agent.db"

def get_connection() -> sqlite3.Connection:
    """Creates a connection to the SQLite database."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)

def extract_state(content: str) -> str:
    """Extracts state from markdown content."""
    # 1. Look for Key: Value pair ("Status: OPEN" or "State: DRAFT")
    match = re.search(r'^(?:Status|State):\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
        
    # 2. Look for Header based status (Common in ADRs)
    match = re.search(r'^##\s*(?:Status|State)\s*\n+([A-Za-z]+)', content, re.MULTILINE)
    if match:
        return match.group(1).strip().upper()
        
    return "UNKNOWN"

def extract_related_stories(content: str) -> Set[str]:
    """Extracts related story IDs from Plan markdown."""
    stories = set()
    section_match = re.search(r'^##\s+Related Stor(?:y|ies)(.*?)(^##|\Z)', content, re.DOTALL | re.MULTILINE)
    if section_match:
        section_content = section_match.group(1)
        # Format: PRE-123 or STORY-123
        ids = re.findall(r'\b[A-Z]+-\d+\b', section_content)
        for i in ids:
            stories.add(i)
    return stories

def extract_linked_adrs(content: str) -> Set[str]:
    """Extracts linked ADR IDs from Story markdown."""
    adrs = set()
    section_match = re.search(r'^##\s+Linked ADRs(.*?)(^##|\Z)', content, re.DOTALL | re.MULTILINE)
    if section_match:
        section_content = section_match.group(1)
        # Format: ADR-001
        ids = re.findall(r'\bADR-\d+\b', section_content)
        for i in ids:
            adrs.add(i)
    return adrs

def upsert_artifact(id: str, type: str, content: str, author: str = "agent") -> bool:
    """Inserts or updates an artifact in the local cache and manages links."""
    # Retry loop for auto-initialization
    for attempt in range(2):
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = get_connection()
            conn.execute("PRAGMA foreign_keys = ON") 
            cursor = conn.cursor()
            
            # Check if exists (using composite key)
            cursor.execute("SELECT version FROM artifacts WHERE id = ? AND type = ?", (id, type))
            row = cursor.fetchone()
            version = 1
            if row:
                version = row[0] + 1
                
            # Compliance: Scrub content before persistence
            content = scrub_sensitive_data(content)
                
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
            # 1. Clear existing links from this source
            cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (id, type))
            
            # 2. Parse and Insert new links
            if type == "plan":
                related_stories = extract_related_stories(content)
                for story_id in related_stories:
                    # Check existence to ensure FK stability
                    cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'story'", (story_id,))
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                            VALUES (?, ?, ?, ?, ?)
                        """, (id, type, story_id, "story", "contains"))
                    else:
                        # In a distributed system, a missing link target is common (not yet pulled).
                        # We gracefully skip it for now.
                        pass

            elif type == "story":
                linked_adrs = extract_linked_adrs(content)
                for adr_id in linked_adrs:
                    cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'adr'", (adr_id,))
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                            VALUES (?, ?, ?, ?, ?)
                        """, (id, type, adr_id, "adr", "related"))

            elif type == "runbook":
                # Runbook ID usually == Story ID
                story_id = id
                cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = 'story'", (story_id,))
                if cursor.fetchone():
                    cursor.execute("""
                            INSERT INTO links (source_id, source_type, target_id, target_type, rel_type)
                            VALUES (?, ?, ?, ?, ?)
                        """, (id, type, story_id, "story", "implements"))

            conn.commit()
            return True

        except sqlite3.OperationalError as e:
            if "no such table" in str(e) and attempt == 0:
                print(f"Database table missing, initializing schema... ({e})")
                if conn:
                    conn.close()
                init_db()
                continue
            else:
                print(f"Operational error in DB: {e}")
                return False

        except Exception as e:
            print(f"Warning: Failed to sync to local DB: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if conn:
                conn.close()
                
    return False

def get_artifact_counts() -> dict:
    """Returns a count of artifacts by type."""
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Check if table exists first preventing crash on fresh install
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
            return {}
            
        cursor.execute("SELECT type, COUNT(*) FROM artifacts GROUP BY type")
        return dict(cursor.fetchall())
    except sqlite3.OperationalError:
        return {}
    except Exception as e:
        print(f"Error checking status: {e}")
        return {}
        if conn:
            conn.close()

def get_all_artifacts_content(artifact_id: Optional[str] = None) -> list:
    """Returns all artifacts including content from the local cache."""
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
            return []
            
        if artifact_id:
            cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
        else:
            cursor.execute("SELECT * FROM artifacts")
            
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    except Exception as e:
        print(f"Error fetching artifacts: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_artifacts_metadata() -> list:
    """Returns metadata for all artifacts in the local cache."""
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
            return []
            
        cursor.execute("SELECT id, type, version, state, author, last_modified FROM artifacts ORDER BY id DESC, type")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return []
        if conn:
            conn.close()

def delete_artifact(id: str, type: Optional[str] = None) -> bool:
    """Deletes an artifact from the local cache."""
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        if type:
            # Check existence
            cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = ?", (id, type))
            if not cursor.fetchone():
                print(f"Artifact {id} (type={type}) not found.")
                return False

            print(f"Deleting {id} ({type})...")
            # Deletions propagate via FKs if ON DELETE CASCADE is set, 
            # but our schema.sql uses default (NO ACTION or RESTRICT).
            # So we manually clear children first to be safe.
            cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (id, type))
            cursor.execute("DELETE FROM links WHERE target_id = ? AND target_type = ?", (id, type))
            cursor.execute("DELETE FROM history WHERE artifact_id = ? AND artifact_type = ?", (id, type))
            cursor.execute("DELETE FROM artifacts WHERE id = ? AND type = ?", (id, type))
        else:
            # Delete all types with this ID
            cursor.execute("SELECT type FROM artifacts WHERE id = ?", (id,))
            rows = cursor.fetchall()
            if not rows:
                print(f"Artifact {id} not found.")
                return False
                
            for row in rows:
                art_type = row[0]
                print(f"Deleting {id} ({art_type})...")
                cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (id, art_type))
                cursor.execute("DELETE FROM links WHERE target_id = ? AND target_type = ?", (id, art_type))
                cursor.execute("DELETE FROM history WHERE artifact_id = ? AND artifact_type = ?", (id, art_type))
                cursor.execute("DELETE FROM artifacts WHERE id = ? AND type = ?", (id, art_type))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting artifact: {e}")
        return False
    finally:
        if conn:
            conn.close()
