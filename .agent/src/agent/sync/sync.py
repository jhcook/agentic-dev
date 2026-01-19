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

from agent.db.client import get_artifact_counts, get_artifacts_metadata, delete_artifact
from agent.sync.pagination import fetch_page
from agent.sync.progress import ProgressTracker


def read_checkpoint() -> int:
    # This function should be implemented to read from a checkpoint store.
    return 0

def save_checkpoint(cursor: int):
    # This function should be implemented to save to a checkpoint store.
    pass

def get_total_artifacts() -> int:
    # This function should interact with Supabase to fetch total count of artifacts.
    # Return 0 for now to prevent crash
    return 0

def process_page(page):
    # Processes each page of artifacts.
    pass

def sync():
    total = get_total_artifacts()  # Fetch total count from Supabase
    tracker = ProgressTracker(total)
    page_size = int(os.getenv("AGENT_SYNC_PAGE_SIZE", 100))
    cursor = read_checkpoint() or 0

    while cursor < total:
        try:
            page = fetch_page(cursor, page_size)
            process_page(page)
            cursor += len(page)  # Ensure cursor progresses by actual page size received
            tracker.update(len(page))
            save_checkpoint(cursor)
        except KeyboardInterrupt:
            print("Sync interrupted. Saving progress...")
            save_checkpoint(cursor)
            break

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

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync artifacts")
    subparsers = parser.add_subparsers(dest="command")
    
    # pull
    subparsers.add_parser("pull", help="Pull artifacts from remote")
    
    # push
    subparsers.add_parser("push", help="Push artifacts to remote")
    
    # status
    status_parser = subparsers.add_parser("status", help="Check sync status")
    status_parser.add_argument("--detailed", action="store_true", help="Show detailed list of artifacts")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete artifact from local cache")
    delete_parser.add_argument("id", help="Artifact ID to delete")
    delete_parser.add_argument("--type", help="Specific artifact type (story, plan, runbook, adr)")
    
    args = parser.parse_args()
    
    if args.command == "pull":
        sync()
    elif args.command == "push":
        print("Push functionality not yet implemented.")
    elif args.command == "status":
        status(detailed=args.detailed)
    elif args.command == "delete":
        delete(args.id, args.type)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
