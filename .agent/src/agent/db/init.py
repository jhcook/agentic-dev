import sqlite3
import os
import sys
from pathlib import Path

def get_db_path() -> Path:
    """Returns the path to the local SQLite database."""
    # Assuming run from repo root or .agent/src
    # We want .agent/cache/agent.db
    # Find .agent root
    current = Path.cwd()
    agent_dir = current / ".agent"
    if not agent_dir.exists():
        # Try to find from src?
        # Fallback to looking up
        pass 
    
    # Just use absolute path relative to CWD if we assume CWD is repo root
    cache_dir = agent_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "agent.db"

def init_db():
    """Initializes the SQLite database with schema."""
    db_path = get_db_path()
    print(f"Initializing database at {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read schema
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}")
        sys.exit(1)
        
    with open(schema_path, "r") as f:
        schema_sql = f.read()
        
    try:
        cursor.executescript(schema_sql)
        conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
