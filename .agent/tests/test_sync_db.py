import pytest
import sqlite3
import os
from pathlib import Path
from agent.db.client import upsert_artifact, get_connection

@pytest.fixture
def mock_db(tmp_path):
    """Fixture to set up a temporary SQLite DB."""
    # We need to patch get_db_path to use tmp_path
    # For simplicity in this test, we can just use the connection directly 
    # if we could inject it, but the client functions instantiate their own.
    # So we will rely on patching or environment var if supported.
    # The client.py hardcodes .agent/cache/agent.db.
    # We will temporarily mock the path return.
    
    db_path = tmp_path / "agent.db"
    
    # Initialize schema
    conn = sqlite3.connect(db_path)
    with open(".agent/src/agent/db/schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.close()
    
    return db_path

def test_upsert_artifact_and_links(mock_db, monkeypatch):
    """Test inserting artifacts and linking logic."""
    
    # Monkeypatch get_db_path in client
    import agent.db.client
    monkeypatch.setattr(agent.db.client, "get_db_path", lambda: mock_db)
    
    # 1. Create a Story
    story_content = """# STORY-1: Test
## Linked ADRs
- ADR-001
"""
    assert upsert_artifact("STORY-1", "story", story_content) == True
    
    # 2. Check DB content
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, version FROM artifacts WHERE id='STORY-1'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "STORY-1"
    
    # 3. Check ADR Link (Note: ADR-001 doesn't exist, so link might be skipped or warn)
    # The current logic checks existence: `SELECT 1 FROM artifacts WHERE id = ? AND type = 'adr'`
    # So we expect NO link yet.
    cursor.execute("SELECT * FROM links WHERE source_id='STORY-1'")
    assert cursor.fetchone() is None
    
    # 4. Create the ADR
    assert upsert_artifact("ADR-001", "adr", "# ADR 1") == True
    
    # 5. Re-upsert the Story (triggering link creation now that ADR exists)
    assert upsert_artifact("STORY-1", "story", story_content) == True
    
    # 6. Verify Link
    cursor.execute("SELECT target_id, rel_type FROM links WHERE source_id='STORY-1'")
    link_row = cursor.fetchone()
    assert link_row is not None
    assert link_row[0] == "ADR-001"
    assert link_row[1] == "related"
    
    conn.close()
