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

def main():
    parser = argparse.ArgumentParser(description="Agent Sync Tool")
    subparsers = parser.add_subparsers(dest="command")
    
    push_parser = subparsers.add_parser("push", help="Push changes to remote")
    pull_parser = subparsers.add_parser("pull", help="Pull changes from remote")
    status_parser = subparsers.add_parser("status", help="Show sync status")
    
    args = parser.parse_args()
    
    if args.command == "push":
        push(args)
    elif args.command == "pull":
        pull(args)
    elif args.command == "status":
        status(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
