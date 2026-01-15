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

import argparse
import os
import sqlite3
import sys
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from supabase import create_client, Client, ClientOptions

# Try to import from agent package, assuming PYTHONPATH is set or installed
try:
    from agent.db.client import upsert_artifact
except ImportError:
    # Fallback for direct script execution if PYTHONPATH not set
    # (Though in this env it usually is)
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from agent.db.client import upsert_artifact

def get_config() -> Dict[str, Any]:
    """Reads sync.yaml configuration."""
    # Assuming run from repo root
    config_path = Path(".agent/etc/sync.yaml")
    if not config_path.exists():
        # Fallback to absolute check if CWD is weird
        pass

    config: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            loaded = yaml.safe_load(f)
            if loaded:
                config = loaded
        
    # Check for .env file for local secrets
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key.strip() == "SUPABASE_ACCESS_TOKEN":
                         os.environ["SUPABASE_ACCESS_TOKEN"] = value.strip().strip('"').strip("'")

    # Check for secrets directory
    secret_path = Path(".agent/secrets/supabase_access_token")
    if secret_path.exists():
         os.environ["SUPABASE_ACCESS_TOKEN"] = secret_path.read_text().strip()

    api_key = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not api_key:
        # Warn but don't fail if just checking status locally  
        # We only print this warning if verbose or if strictly needed?
        # Keeping it for now but maybe quieter.
        pass 
        
    config["supabase_api_key"] = api_key
    return config

def get_supabase_client() -> Client:
    """Creates a Supabase client."""
    config = get_config()
    url = config.get("supabase_url")
    key = config.get("supabase_api_key")
    
    if not url or not key:
        raise ValueError("Missing supabase_url or SUPABASE_ACCESS_TOKEN. Check .agent/etc/sync.yaml and secrets.")
        
    return create_client(url, key)

def get_db_connection() -> sqlite3.Connection:
    """Connects to the local SQLite database."""
    # We use the fixed path relative to repo root
    db_path = Path(".agent/cache/agent.db")
    
    # If not exists, strict fail? Or init?
    if not db_path.exists():
        # Try to init implicitly?
        # print(f"Database not found at {db_path}. Run 'python .agent/src/agent/db/init.py' first.")
        # sys.exit(1)
        pass # Let sqlite3 connect create it, but schema might be missing.
        
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def push(args: argparse.Namespace) -> None:
    """Pushes local changes to remote."""
    try:
        sb = get_supabase_client()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("Sync Push: Reading local state...")
        
        # 1. Artifacts
        cursor.execute("SELECT * FROM artifacts")
        artifacts = [dict(row) for row in cursor.fetchall()]
        
        # 2. History
        cursor.execute("SELECT * FROM history")
        history = [dict(row) for row in cursor.fetchall()]
        
        # 3. Links
        cursor.execute("SELECT * FROM links")
        links = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        if not artifacts:
            print("No local artifacts to push.")
            return

        print(f"Pushing {len(artifacts)} asrtifacts, {len(history)} history entries, {len(links)} links to Supabase...")
        
        # Chunking might be needed for large datasets, but starting simple
        # Supabase Python client upsert
        
        # Artifacts
        if artifacts:
            res = sb.table("artifacts").upsert(artifacts).execute()
        
        # History
        # Note: History might grow large.
        if history:
            res = sb.table("history").upsert(history).execute()
            
        # Links
        if links:
            res = sb.table("links").upsert(links).execute()
            
        print("Push complete.")
        
    except Exception as e:
        print(f"Error during push: {e}")
        # import traceback
        # traceback.print_exc()

def pull(args: argparse.Namespace) -> None:
    """Pulls remote changes to local."""
    try:
        sb = get_supabase_client()
        
        print("Sync Pull: Fetching remote state...")
        
        # 1. Artifacts
        # TODO: Pagination for large datasets
        res = sb.table("artifacts").select("*").execute()
        remote_artifacts = res.data
        
        # Upsert to local DB
        # We shouldn't brute-force replace everything if we want to support offline editing?
        # For now, strict sync: Remote -> Local. 
        # But wait, upsert_artifact handles logic. But here we have raw rows.
        # Let's use raw SQL upsert for efficiency and fidelity.
        
        conn = get_db_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        
        print(f"Received {len(remote_artifacts)} artifacts from remote.")
        
        for art in remote_artifacts:
            # We can use our db/client logic, or raw SQL. 
            # Raw SQL ensures we get exactly what's remote, including timestamps.
            # However, local client.upsert_artifact has logic for history generation?
            # If we pull, we assume history is also pulled.
            
            conn.execute("""
                INSERT OR REPLACE INTO artifacts (id, type, content, last_modified, version, state, author, created_at, updated_at, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art['id'], art['type'], art['content'], art['last_modified'], 
                art['version'], art['state'], art['author'], art['created_at'],
                art['updated_at'], art['owner_id']
            ))
            
        # 2. History
        res = sb.table("history").select("*").execute()
        remote_history = res.data
        for hist in remote_history:
             conn.execute("""
                INSERT OR REPLACE INTO history (change_id, artifact_id, artifact_type, timestamp, author, description, delta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                hist['change_id'], hist['artifact_id'], hist['artifact_type'], 
                hist['timestamp'], hist['author'], hist['description'], hist['delta']
            ))

        # 3. Links
        res = sb.table("links").select("*").execute()
        remote_links = res.data
        for link in remote_links:
             conn.execute("""
                INSERT OR REPLACE INTO links (source_id, source_type, target_id, target_type, rel_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                link['source_id'], link['source_type'], link['target_id'], 
                link['target_type'], link['rel_type'], link['created_at']
            ))
            
        conn.commit()
        conn.close()
        print("Pull complete.")

    except Exception as e:
        print(f"Error during pull: {e}")

def status(args: argparse.Namespace) -> None:
    """Shows sync status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table exists first to avoid crash on fresh repo
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
             print("Local database empty (no artifacts table). Run 'agent sync scan' first.")
             return

        cursor.execute("SELECT id, type, version, state, author FROM artifacts ORDER BY id DESC")
        local_artifacts = cursor.fetchall()
        print("Local Repository Status:")
        print(f"Total Artifacts: {len(local_artifacts)}")
        print("-" * 40)
        print(f"{'ID':<20} | {'Type':<10} | {'Ver':<5} | {'State':<10}")
        print("-" * 40)
        for arti in local_artifacts:
            print(f"{arti['id']:<20} | {arti['type']:<10} | {arti['version']:<5} | {arti['state'] or 'Unknown':<10}")
        conn.close()
    except Exception as e:
        print(f"Error checking status: {e}")

def scan(args: argparse.Namespace) -> None:
    """Scans local directories and ingests artifacts into SQLite."""
    # Logic moved from main block
    
    repo_root = Path.cwd() # Assuming run from root
    
    # Define mapping of Directory -> Type
    dirs_to_scan = [
        (repo_root / ".agent/adrs", "adr"),
        (repo_root / ".agent/cache/stories", "story"),
        (repo_root / ".agent/cache/plans", "plan"),
        (repo_root / ".agent/cache/runbooks", "runbook")
    ]
    
    count = 0
    print("Scanning for artifacts...")
    
    # Initialize DB schema if needed
    # (By calling upsert logic, connection is handled, but schema? 
    #  upsert_artifact assumes schema exists)
    # Let's run init if strictly needed, or assume user ran init
    # We'll just tryupsert.
    
    for dir_path, artifact_type in dirs_to_scan:
        if not dir_path.exists():
            continue
            
        # Recursive glob for markdown files
        for file_path in dir_path.rglob("*.md"):
            if file_path.name.startswith("template"):
                continue
                
            try:
                content = file_path.read_text(errors="ignore")
                
                # Extract ID from filename. 
                stem = file_path.stem
                if "-" in stem:
                    # Attempt to grab prefix-number e.g. INFRA-123
                    match = re.search(r'^([A-Z]+-\d+)', stem)
                    if match:
                        art_id = match.group(1)
                    else:
                        art_id = stem # Fallback
                else:
                    art_id = stem
                    
                print(f"Ingesting {artifact_type.upper()}: {art_id}")
                upsert_artifact(art_id, artifact_type, content, author="scanner")
                count += 1
            except Exception as e:
                print(f"Failed to ingest {file_path}: {e}")
                
    print(f"Scan complete. Ingested {count} artifacts.")

def delete(args: argparse.Namespace) -> None:
    """Deletes an artifact from the local database."""
    try:
        conn = get_db_connection()
        # Verify schema exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        if not cursor.fetchone():
             print("Database not initialized.")
             conn.close()
             return

        conn.execute("PRAGMA foreign_keys = ON")
        
        # Determine strictness
        if args.type:
            cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = ?", (args.id, args.type))
            if not cursor.fetchone():
                print(f"Artifact {args.id} (type={args.type}) not found.")
                conn.close()
                return

            print(f"Deleting {args.id} ({args.type})...")
            # Manual cascade (safeguard)
            cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (args.id, args.type))
            cursor.execute("DELETE FROM links WHERE target_id = ? AND target_type = ?", (args.id, args.type))
            cursor.execute("DELETE FROM history WHERE artifact_id = ? AND artifact_type = ?", (args.id, args.type))
            cursor.execute("DELETE FROM artifacts WHERE id = ? AND type = ?", (args.id, args.type))
        else:
            # Delete all types with this ID
            cursor.execute("SELECT type FROM artifacts WHERE id = ?", (args.id,))
            rows = cursor.fetchall()
            if not rows:
                print(f"Artifact {args.id} not found.")
                conn.close()
                return
                
            for row in rows:
                art_type = row[0]
                print(f"Deleting {args.id} ({art_type})...")
                cursor.execute("DELETE FROM links WHERE source_id = ? AND source_type = ?", (args.id, art_type))
                cursor.execute("DELETE FROM links WHERE target_id = ? AND target_type = ?", (args.id, art_type))
                cursor.execute("DELETE FROM history WHERE artifact_id = ? AND artifact_type = ?", (args.id, art_type))
                cursor.execute("DELETE FROM artifacts WHERE id = ? AND type = ?", (args.id, art_type))

        conn.commit()
        conn.close()
        print("Delete successful.")
        
    except Exception as e:
        print(f"Error deleting artifact: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Sync Tool")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("push", help="Push changes to remote")
    subparsers.add_parser("pull", help="Pull changes from remote")
    subparsers.add_parser("status", help="Show sync status")
    subparsers.add_parser("scan", help="Scan and ingest local artifacts")
    
    delete_parser = subparsers.add_parser("delete", help="Delete artifact from local DB")
    delete_parser.add_argument("id", help="Artifact ID to delete")
    delete_parser.add_argument("--type", help="Specific artifact type (story, plan, runbook, adr)")
    
    args = parser.parse_args()
    
    if args.command == "push":
        push(args)
    elif args.command == "pull":
        pull(args)
    elif args.command == "status":
        status(args)
    elif args.command == "scan":
        scan(args)
    elif args.command == "delete":
        delete(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
