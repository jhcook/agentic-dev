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
import os
import re
import requests
import json
import sys

def get_last_session_file():
    """Find the most recent session file in .agent/storage/voice_sessions."""
    storage_dir = ".agent/storage/voice_sessions"
    if not os.path.exists(storage_dir):
        return None
        
    files = [os.path.join(storage_dir, f) for f in os.listdir(storage_dir) if f.endswith(".json")]
    if not files:
        return None
        
    # Python file timestamps are reliable enough for latest
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def get_last_session_id(log_path):
    """Scan log file for the last 'Orchestrator worker started' event."""
    if not os.path.exists(log_path):
        return None
        
    session_id = None
    with open(log_path, 'r') as f:
        for line in f:
            match = re.search(r"session ([a-f0-9\-]{36})", line)
            if match:
                session_id = match.group(1)
    return session_id

def main():
    # 1. Try file storage first (Persistent)
    last_file = get_last_session_file()
    if last_file:
        try:
            with open(last_file, 'r') as f:
                print(f.read())
            sys.exit(0)
        except Exception as e:
            pass
            
    # 2. Fallback to API checks
    log_file = ".agent/logs/admin_backend.log"
    session_id = get_last_session_id(log_file)
    
    if not session_id:
        print(json.dumps({"error": "No session found in logs."}))
        sys.exit(1)
        
    try:
        url = f"http://localhost:8000/history/{session_id}"
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            print(json.dumps(resp.json(), indent=2))
        else:
            print(json.dumps({"error": f"API returned {resp.status_code}", "session_id": session_id}))
    except Exception as e:
        print(json.dumps({"error": str(e), "session_id": session_id}))

if __name__ == "__main__":
    main()
