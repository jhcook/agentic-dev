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
import os
import re
from pathlib import Path

import typer

from agent.db.client import (
    delete_artifact,
    get_all_artifacts_content,
    get_artifact_counts,
    get_artifacts_metadata,
    upsert_artifact,
)
from agent.sync.client import get_supabase_client
from agent.sync.pagination import fetch_page
from agent.sync.progress import ProgressTracker


def read_checkpoint() -> int:
    # This function should be implemented to read from a checkpoint store.
    # For now, we always start from 0 for a full sync if we don't have a persistent checkpoint mechanism
    return 0

def save_checkpoint(cursor: int):
    # This function should be implemented to save to a checkpoint store.
    pass

def get_total_artifacts(client) -> int:
    """Fetch total count of artifacts from Supabase."""
    try:
        # head=True means we only get the count, not the data
        count = client.table('artifacts').select("*", count='exact', head=True).execute().count
        return count if count is not None else 0
    except Exception as e:
        print(f"Error fetching total count: {e}")
        return 0

def process_page(page):
    """Processes each page of artifacts by upserting them to the local DB."""
    if not page:
        return
        
    for item in page:
        try:
            # Upsert into local SQLite
            # Item keys match Supabase columns: id, type, content, etc.
            # We map them to upsert_artifact arguments
            upsert_artifact(
                id=item.get('id'),
                type=item.get('type'),
                content=item.get('content'),
                author=item.get('author', 'remote')
            )
        except Exception as e:
            print(f"Error processing artifact {item.get('id')}: {e}")

from agent.commands.secret import _prompt_password
from agent.core.secrets import get_secret_manager



def pull(verbose: bool = False, backend: str = None, force: bool = False, artifact_id: str = None, artifact_type: str = None):
    """
    Execute the sync process (pull from remote).
    
    Status Mapping:
      - Notion 'Status' property (Select/Status) maps to the 'State' metadata in Markdown artifacts.
      - e.g., Notion "In Progress" -> Markdown "State: IN_PROGRESS" (normalized to uppercase/underscore).
      - This allows bi-directional sync of workflow states.
    """
    
    # Backend Orchestration
    run_all = backend is None
    
    # 1. Supabase (Core)
    if run_all or backend in ["supabase", "core"]:
        _pull_supabase(verbose, strict=(backend in ["supabase", "core"])) # TODO: Pass artifact_id filter to supabase logic
        
    # 2. Notion
    if run_all or backend == "notion":
        from agent.sync.notion import NotionSync
        try:
            print("Syncing with Notion...")
            NotionSync().pull(force=force, artifact_id=artifact_id, artifact_type=artifact_type)
        except Exception as e:
            print(f"Notion sync failed: {e}")

def _pull_supabase(verbose: bool = False, strict: bool = False):
    """Internal Supabase Pull Logic"""
    client = get_supabase_client(verbose=verbose)
    
    # interactive unlock if client is None
    if not client:
        manager = get_secret_manager()
        if manager.is_initialized() and not manager.is_unlocked():
            print("Secrets found but manager is locked.")
            if typer.confirm("Unlock secret manager?", default=True):
                try:
                    password = _prompt_password()
                    manager.unlock(password)
                    print("Manager unlocked. Retrying...")
                    client = get_supabase_client(verbose=verbose)
                except Exception as e:
                    print(f"Failed to unlock: {e}")

    if not client:
        if strict or verbose:
            print("Cannot sync: Supabase client not initialized. Check credentials.")
            if verbose:
                print("Tip: Run 'agent secret set supabase service_role_key' or set SUPABASE_SERVICE_ROLE_KEY env var.")
        return

    total = get_total_artifacts(client)  # Fetch total count from Supabase
    
    if total == 0:
        print("No artifacts found on remote.")
        return
        
    tracker = ProgressTracker(total)
    page_size = int(os.getenv("AGENT_SYNC_PAGE_SIZE", 100))
    cursor = read_checkpoint() or 0

    print(f"Syncing {total} artifacts from remote...")

    while cursor < total:
        try:
            page = fetch_page(client, cursor, page_size)
            if not page:
                break
                
            process_page(page)
            
            # Update cursor and progress
            count = len(page)
            cursor += count
            tracker.update(count)
            save_checkpoint(cursor)
            
        except KeyboardInterrupt:
            print("\nSync interrupted. Saving progress...")
            save_checkpoint(cursor)
            break
        except Exception as e:
            print(f"\nError during sync: {e}")
            break

def push(verbose: bool = False, backend: str = None, force: bool = False, artifact_id: str = None, artifact_type: str = None):
    """Push local artifacts to remote."""
    
    # Backend Orchestration
    run_all = backend is None
    
    # 1. Supabase (Core)
    if run_all or backend in ["supabase", "core"]:
        _push_supabase(verbose, artifact_id, strict=(backend in ["supabase", "core"])) # Type filtering not strictly needed for Supabase yet (ID is unique per table usually, but good to add later)
        
    # 2. Notion
    if run_all or backend == "notion":
        from agent.sync.notion import NotionSync
        try:
            print("Syncing with Notion...")
            NotionSync().push(force=force, artifact_id=artifact_id, artifact_type=artifact_type)
        except Exception as e:
            print(f"Notion sync failed: {e}")

def _push_supabase(verbose: bool = False, artifact_id: str = None, strict: bool = False):
    """Internal Supabase Push Logic"""
    client = get_supabase_client(verbose=verbose)
    
    # interactive unlock if client is None
    if not client:
        manager = get_secret_manager()
        if manager.is_initialized() and not manager.is_unlocked():
            print("Secrets found but manager is locked.")
            if typer.confirm("Unlock secret manager?", default=True):
                try:
                    password = _prompt_password()
                    manager.unlock(password)
                    print("Manager unlocked. Retrying...")
                    client = get_supabase_client(verbose=verbose)
                except Exception as e:
                    print(f"Failed to unlock: {e}")

    if not client:
        if strict or verbose:
            print("Cannot push: Supabase client not initialized. Check credentials.")
            if verbose:
                print("Tip: Run 'agent secret set supabase service_role_key' or set SUPABASE_SERVICE_ROLE_KEY env var.")
        return

    artifacts = get_all_artifacts_content(artifact_id)
    if not artifacts:
        print("No local artifacts to push.")
        return

    print(f"Pushing {len(artifacts)} artifacts to remote...")
    
    success_count = 0
    error_count = 0
    
    for art in artifacts:
        try:
            # Prepare payload matching Supabase schema
            payload = {
                "id": art["id"],
                "type": art["type"],
                "content": art["content"],
                "version": art["version"],
                "state": art["state"],
                "author": art["author"],
                # Let Supabase handle timestamps or use local modified time?
                # Using upsert
            }
            
            client.table("artifacts").upsert(payload).execute()
            success_count += 1
            if verbose:
                print(f"  Pushed {art['id']}")
                
        except Exception as e:
            error_count += 1
            print(f"Failed to push {art.get('id')}: {e}")

    print(f"Push complete. {success_count} success, {error_count} errors.")

def push_safe(timeout: int = 2, verbose: bool = False, artifact_id: str = None):
    """
    Executes a 'Best Effort' push.
    Designed for secondary targets (like Notion) that should not block the CLI.
    Swallows errors and enforces a strict timeout.
    """
    import signal
    import threading

    def _target():
        try:
            push(verbose=verbose, backend=None, force=False, artifact_id=artifact_id)
        except Exception:
            pass # Swallow internal errors
    
    # Run in thread to enforce timeout
    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=timeout)
    
    if t.is_alive():
        if verbose:
            print(f"[WARN] Sync timed out after {timeout}s (Background)")
        # We can't easily kill python threads, but we abandon it.
        # This prevents the CLI from hanging.


def status(detailed: bool = False):
    """Checks and prints the sync status."""
    print("Sync Status:")
    counts = get_artifact_counts()
    if not counts:
        print("  No local artifacts cache found.")
        print("  (Run 'agent sync pull' to populate cache)")
        return

    print("  Local Artifacts Summary:")
    for type, count in counts.items():
        print(f"    - {type.title()}: {count}")
    
    # Simple logic: Show detailed if requested OR if total count is small (< 50)
    total_count = sum(counts.values())
    
    if detailed or total_count < 50:
        print("\n  Detailed Inventory:")
        print(f"  {'-'*75}")
        print(f"  {'ID':<25} | {'Type':<10} | {'Ver':<5} | {'State':<15} | {'Author':<10}")
        print(f"  {'-'*75}")
        
        artifacts = get_artifacts_metadata()
        for art in artifacts:
            # Handle None values gracefully
            art_id = art.get('id', 'N/A')
            art_type = art.get('type', 'N/A')
            version = art.get('version', 1)
            state = art.get('state') or 'UNKNOWN'
            author = art.get('author') or 'agent'
            
            # Truncate if too long
            if len(art_id) > 23: art_id = art_id[:20] + "..."
            
            print(f"  {art_id:<25} | {art_type:<10} | {version:<5} | {state:<15} | {author:<10}")
        print(f"  {'-'*75}")
    else:
        print(f"\n  (Use --detailed to see list of {total_count} artifacts)")

def delete(id: str, type: str = None):
    """Deletes an artifact."""
    success = delete_artifact(id, type)
    if success:
        print("Delete successful.")
    else:
        print("Delete failed.")

def scan(verbose: bool = False):
    """Scans local directories and populates the artifact database."""
    base_dir = Path(".agent/cache")
    # Also check .agent/adrs which is standard location
    adr_dir = Path(".agent/adrs")
    
    if not base_dir.exists() and not adr_dir.exists():
        print("No artifact directories found to scan.")
        return

    # Standard paths
    paths_to_scan = [
        (Path(".agent/cache/stories"), "story"),
        (Path(".agent/cache/plans"), "plan"),
        (Path(".agent/cache/runbooks"), "runbook"),
        (adr_dir, "adr"),
    ]

    total_added = 0
    total_errors = 0

    print("Scanning local artifacts...")
    
    for path, type in paths_to_scan:
        if not path.exists():
            if verbose: print(f"Skipping missing directory: {path}")
            continue

        for file in path.rglob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                
                # Extract ID from filename (e.g., INFRA-001-description.md -> INFRA-001)
                filename = file.name
                match = re.match(r"^([A-Z]+-\d+)", filename)
                if match:
                    art_id = match.group(1)
                else:
                    # Fallback
                    art_id = filename.replace(".md", "")

                if verbose:
                    print(f"  Found {type.upper()}: {art_id} ({file})")

                # Upsert
                if upsert_artifact(art_id, type, content, author="scanner"):
                    total_added += 1
                else:
                    total_errors += 1
                    print(f"Failed to upsert {art_id}")

            except Exception as e:
                total_errors += 1
                print(f"Error processing {file}: {e}")

    print(f"Scan complete. Processed {total_added} artifacts with {total_errors} errors.")



def janitor(
    notion_api_key: str = None, 
    database_id: str = None, 
    dry_run: bool = False,
    backend: str = None
):
    """Run the Janitor to maintain relational integrity."""
    
    # Default to Notion if not specified, or if specific backend requested
    if backend is None or backend == "notion":
        from agent.core.notion.client import NotionClient
        from agent.sync.janitor import NotionJanitor
        from agent.core.secrets import get_secret
        
        # Resolve Credentials
        if not notion_api_key:
            notion_api_key = get_secret("notion_token", service="agent") or os.getenv("NOTION_TOKEN")
            
        if not notion_api_key:
            print("Error: Notion API Key not found. Set NOTION_TOKEN or use --notion-api-key.")
            return

        # Resolve Database ID
        if not database_id:
             database_id = os.getenv("NOTION_DB_ID")
             
        if not database_id:
            print("Error: Notion Database ID not found. Set NOTION_DB_ID or use --database-id.")
            return

        print("Running Notion Janitor...")
        client = NotionClient(notion_api_key)
        janitor = NotionJanitor(client)
        janitor.run_janitor(database_id)
    else:
        print(f"Janitor backend '{backend}' not supported.")

def init(backend: str = None):
    """Bootstraps the sync environment (e.g. Notion databases)."""
    if backend is None or backend == "notion":
        from agent.sync.bootstrap import NotionBootstrap
        try:
            print("Bootstrapping Notion backend...")
            NotionBootstrap().run()
        except Exception as e:
            print(f"Notion bootstrap failed: {e}")
    else:
        print(f"Backend '{backend}' does not support initialization.")
