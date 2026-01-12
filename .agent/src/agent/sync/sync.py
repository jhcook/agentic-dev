import argparse
import os
import sqlite3
import sys
import yaml
from pathlib import Path

def get_config():
    """Reads sync.yaml configuration."""
    # Assuming run from repo root
    config_path = Path(".agent/etc/sync.yaml")
    if not config_path.exists():
        print(f"Config file not found: {config_path.absolute()}")
        sys.exit(1)
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    # Check for .env file for local secrets
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key.strip() == "SUPABASE_SERVICE_ROLE_KEY":
                         os.environ["SUPABASE_SERVICE_ROLE_KEY"] = value.strip().strip('"').strip("'")

    # Check for secrets directory
    secret_path = Path(".agent/secrets/supabase_key")
    if secret_path.exists():
         os.environ["SUPABASE_SERVICE_ROLE_KEY"] = secret_path.read_text().strip()

    api_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not api_key:
        # Warn but don't fail if just checking status locally  
        print("Warning: SUPABASE_SERVICE_ROLE_KEY environment variable not set (and not found in .env or .agent/secrets/). Remote operations will fail.")
        
    config["supabase_api_key"] = api_key
    return config

def get_db_connection():
    """Connects to the local SQLite database."""
    db_path = Path(".agent/cache/agent.db")
    if not db_path.exists():
        print(f"Database not found at {db_path}. Run 'python .agent/src/agent/db/init.py' first.")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def push(args):
    """Pushes local changes to remote."""
    config = get_config()
    if not config.get("supabase_api_key"):
        print("Error: Cannot push without SUPABASE_SERVICE_ROLE_KEY.")
        return

    print("Sync Push: Connecting to Supabase...")
    # TODO: Implement Supabase client logic
    print("Push functionality not yet fully implemented (requires Supabase client integration).")

def pull(args):
    """Pulls remote changes to local."""
    config = get_config()
    if not config.get("supabase_api_key"):
        print("Error: Cannot pull without SUPABASE_SERVICE_ROLE_KEY.")
        return

    print("Sync Pull: Connecting to Supabase...")
    # TODO: Implement Supabase client logic
    print("Pull functionality not yet fully implemented (requires Supabase client integration).")

def status(args):
    """Shows sync status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, type, version, state, author FROM artifacts")
        local_artifacts = cursor.fetchall()
        print(f"Local Repository Status:")
        print(f"Total Artifacts: {len(local_artifacts)}")
        print("-" * 40)
        print(f"{'ID':<20} | {'Type':<10} | {'Ver':<5} | {'State':<10}")
        print("-" * 40)
        for arti in local_artifacts:
            print(f"{arti['id']:<20} | {arti['type']:<10} | {arti['version']:<5} | {arti['state'] or 'Unknown':<10}")
        conn.close()
    except Exception as e:
        print(f"Error checking status: {e}")

def scan(args):
    """Scans local directories and ingests artifacts into SQLite."""
    # We need to import upsert_artifact. 
    # Since we are running as a script, we might need to adjust path or use relative imports if module
    try:
        sys.path.append(str(Path(__file__).resolve().parent.parent.parent)) # Add src to path
        from agent.db.client import upsert_artifact
    except ImportError as e:
        print(f"Error importing client: {e}")
        return

    repo_root = Path.cwd() # Assuming run from root
    
    # Define mapping of Directory -> Type
    # Note: Stories are in .agent/cache/stories/<SCOPE>/<ID>.md
    # Plans: .agent/cache/plans/<SCOPE>/<ID>.md (or just flat?)
    # Runbooks: .agent/cache/runbooks/<SCOPE>/<ID>.md
    # ADRs: .agent/adrs/<ID>.md
    
    dirs_to_scan = [
        (repo_root / ".agent/adrs", "adr"),
        (repo_root / ".agent/cache/stories", "story"),
        (repo_root / ".agent/cache/plans", "plan"),
        (repo_root / ".agent/cache/runbooks", "runbook")
    ]
    
    count = 0
    print("Scanning for artifacts...")
    
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
                # Expected: ID-description.md or ID.md
                # e.g. INFRA-004-blah.md -> INFRA-004
                # ADR-001-blah.md -> ADR-001
                stem = file_path.stem
                if "-" in stem:
                    # Attempt to grab prefix-number e.g. INFRA-123
                    import re
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

def delete(args):
    """Deletes an artifact from the local database."""
    try:
        conn = get_db_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Determine strictness
        # If type is provided, use it. If not, check for ambiguity or delete all matching ID.
        if args.type:
            cursor.execute("SELECT 1 FROM artifacts WHERE id = ? AND type = ?", (args.id, args.type))
            if not cursor.fetchone():
                print(f"Artifact {args.id} (type={args.type}) not found.")
                conn.close()
                return

            print(f"Deleting {args.id} ({args.type})...")
            # Manual cascade (safe)
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

def main():
    parser = argparse.ArgumentParser(description="Agent Sync Tool")
    subparsers = parser.add_subparsers(dest="command")
    
    push_parser = subparsers.add_parser("push", help="Push changes to remote")
    pull_parser = subparsers.add_parser("pull", help="Pull changes from remote")
    status_parser = subparsers.add_parser("status", help="Show sync status")
    scan_parser = subparsers.add_parser("scan", help="Scan and ingest local artifacts")
    
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
