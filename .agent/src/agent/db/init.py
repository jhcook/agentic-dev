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

import sqlite3
import sys
from pathlib import Path


def get_db_path() -> Path:
    """Returns the path to the local SQLite database."""
    from agent.core.config import config
    cache_dir = config.cache_dir
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
