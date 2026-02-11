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
from agent.core.config import config
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

def _sanitize_filename(name: str) -> str:
    """Sanitizes a string to be safe for filenames."""
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[-\s]+", "-", name)
    return name[:80]

def _write_to_disk(id: str, type: str, content: str):
    """Writes the artifact content to the local filesystem."""
    try:
        # Determine base directory
        base_dir = None
        if type == "story":
            base_dir = config.stories_dir
        elif type == "plan":
            base_dir = config.plans_dir
        elif type == "runbook":
            base_dir = config.runbooks_dir
        elif type == "adr":
            base_dir = config.adrs_dir
        else:
            # Fallback or unknown type
            return

        # Ensure base directory exists
        base_dir.mkdir(parents=True, exist_ok=True)

        # Extract Title for filename
        lines = content.splitlines()
        title = "Untitled"
        if lines:
            # Assume first line is header: # ID: Title or # Title
            header = lines[0].lstrip("#").strip()
            # Remove ID if present in header
            if header.startswith(id):
                header = header[len(id):].strip().lstrip(":").strip()
            if header:
                title = header

        safe_title = _sanitize_filename(title)
        filename = f"{id}-{safe_title}.md"
        
        # Determine Target Directory (Scope-based subdirs for Stories/Plans)
        target_dir = base_dir
        if type in ["story", "plan"]:
            # Check for scope in ID (e.g., BACKEND-123)
            parts = id.split("-")
            if len(parts) > 1 and parts[0].isalpha():
                scope = parts[0]
                target_dir = base_dir / scope
        
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename

        # Cleanup: Remove duplicates or old filenames from root or other locations
        # This is a basic cleanup: if we are writing to a subdir, check root for matches
        if target_dir != base_dir:
            for existing in base_dir.glob(f"{id}-*.md"):
                try:
                    existing.unlink()
                except Exception:
                    pass
        
        # Check for existing file with same ID but different name (title change)
        for existing in target_dir.glob(f"{id}-*.md"):
            if existing.name != filename:
                try:
                    existing.unlink()
                except Exception:
                    pass

        # Write file
        target_file.write_text(content, encoding="utf-8")
        
    except Exception as e:
        print(f"Failed to write {id} to disk: {e}")

def process_page(page):
    """Processes each page of artifacts by upserting them to the local DB and writing to disk."""
    if not page:
        return
        
    for item in page:
        try:
            id = item.get('id')
            type = item.get('type')
            content = item.get('content')
            author = item.get('author', 'remote')

            # Upsert into local SQLite
            upsert_artifact(
                id=id,
                type=type,
                content=content,
                author=author
            )
            
            # Write to Disk
            if id and type and content:
                _write_to_disk(id, type, content)

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
        from agent.core.config import get_secret
        notion_token = get_secret("notion_token", service="notion") or os.getenv("NOTION_TOKEN")
        
        if notion_token:
            from agent.sync.notion import NotionSync
            try:
                print("Syncing with Notion...")
                NotionSync().pull(force=force, artifact_id=artifact_id, artifact_type=artifact_type)
            except Exception as e:
                print(f"Notion sync failed: {e}")
        elif backend == "notion":
            print("Skipping Notion sync: NOTION_TOKEN not found.")
            
    # Always update local artifact DB after pull
    if run_all or backend == "notion":
        scan(verbose=verbose)

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
        from agent.core.config import get_secret
        notion_token = get_secret("notion_token", service="notion") or os.getenv("NOTION_TOKEN")
        
        if notion_token:
            from agent.sync.notion import NotionSync
            try:
                print("Syncing with Notion...")
                NotionSync().push(force=force, artifact_id=artifact_id, artifact_type=artifact_type)
            except Exception as e:
                print(f"Notion sync failed: {e}")
        elif backend == "notion":
            print("Skipping Notion sync: NOTION_TOKEN not found.")

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
            notion_api_key = get_secret("notion_token", service="notion") or os.getenv("NOTION_TOKEN")
            
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


def flush(hard: bool = False):
    """Deletes local sync state so the next pull refreshes from remote.

    By default, preserves notion_state.json (the DB linkage) so you don't
    need to re-run 'agent sync init'. Use --hard to wipe everything,
    including the Notion DB mapping.
    """
    import shutil
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    state_file = config.cache_dir / "notion_state.json"
    db_file = config.cache_dir / "agent.db"
    artifact_dirs = [config.stories_dir, config.plans_dir, config.runbooks_dir]

    # Summarise what will be deleted
    targets = []
    if db_file.exists():
        targets.append(f"  • {db_file.relative_to(config.repo_root)}")
    for d in artifact_dirs:
        if d.exists() and any(d.iterdir()):
            targets.append(f"  • {d.relative_to(config.repo_root)}/")
    if hard and state_file.exists():
        targets.append(f"  • {state_file.relative_to(config.repo_root)}  [bold red](Notion DB linkage)[/bold red]")

    if not targets:
        console.print("[dim]Nothing to flush — local state is already clean.[/dim]")
        return

    console.print("[bold yellow]The following will be deleted:[/bold yellow]")
    for t in targets:
        console.print(t)

    if hard:
        console.print("\n[bold red]⚠  --hard: Notion DB linkage will be removed. "
                      "You will need to re-run 'agent sync init'.[/bold red]")

    if not Confirm.ask("\nProceed?", default=False):
        console.print("[dim]Aborted.[/dim]")
        return

    # Delete
    if db_file.exists():
        db_file.unlink()
        console.print(f"  [red]✗[/red] Deleted {db_file.name}")

    for d in artifact_dirs:
        if d.exists():
            shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
            console.print(f"  [red]✗[/red] Cleared {d.relative_to(config.repo_root)}/")

    if hard and state_file.exists():
        state_file.unlink()
        console.print(f"  [red]✗[/red] Deleted {state_file.name}")

    console.print("\n[bold green]Flush complete.[/bold green] Run [bold]agent sync pull[/bold] to refresh from remote.")
