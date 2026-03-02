#!/usr/bin/env python3
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

"""Script to fetch the transcript of the last agent console session."""

import json
import sqlite3
from pathlib import Path

def get_last_session_transcript():
    """Fetch the most recent session transcript from the console DB."""
    db_path = Path(".agent/cache/console.db")
    if not db_path.exists():
        return json.dumps({"error": f"Console Database {db_path} not found."})

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find the latest session
        cursor.execute("SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 1")
        session = cursor.fetchone()
        
        if not session:
            return json.dumps({"error": "No sessions found in the database."})

        session_id = session["id"]

        # Fetch messages for that session
        cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
        messages = cursor.fetchall()
        
        if not messages:
            return json.dumps({"error": f"Session {session_id} has no messages."})

        # Build transcript
        transcript = f"Title: {session['title']}\nID: {session_id}\nDate: {session['updated_at']}\n\n"
        for msg in messages:
            role = msg["role"].upper()
            transcript += f"### {role}\n{msg['content']}\n\n"

        return transcript
        
    except sqlite3.Error as e:
         return json.dumps({"error": f"Database error: {e}"})
    finally:
         if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    transcript = get_last_session_transcript()
    print(transcript)
