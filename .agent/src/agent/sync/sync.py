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

import os
import re
from pathlib import Path

from agent.db.client import get_artifact_counts, get_artifacts_metadata, delete_artifact, upsert_artifact
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

def scan(verbose: bool = False):
    """Scans local directories and populates the artifact database."""
    base_dir = Path(".agent/cache")
    # Also check .agent/adrs which is standard location
    adr_dir = Path(".agent/adrs")
    
    if not base_dir.exists() and not adr_dir.exists():
        print(f"No artifact directories found to scan.")
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


