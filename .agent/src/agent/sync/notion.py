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

import difflib
import unicodedata
import concurrent.futures
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.prompt import Confirm

from agent.core.config import config
from agent.core.notion.client import NotionClient
from agent.core.secrets import get_secret

logger = logging.getLogger(__name__)

STATE_FILE = config.cache_dir / "notion_state.json"

# Constants
MAX_STATUS_LENGTH = 50

class NotionSync:
    def __init__(self):
        # Refactored to use 'notion' service for secrets
        self.token = get_secret("notion_token", service="notion")
            
        if not self.token:
            # Fallback to env var
            import os
            self.token = os.getenv("NOTION_TOKEN")
            
        if not self.token:
            logger.debug("NOTION_TOKEN not found. Notion sync is disabled.")
            self.client = None
            self.state = {}
            return

        self.client = NotionClient(self.token)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, str]:
        if not STATE_FILE.exists():
            return {}
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def ensure_synchronized(self) -> None:
        """
        Validates the Notion sync state before allowing Oracle Preflight.
        Logs warning or raises error if the sync state is missing/stale.
        """
        if not self.client:
            return

        if not self.state:
            logger.warning("Notion sync state is missing or invalid.")
            from rich.console import Console
            Console().print("[yellow]⚠️  Notion sync state is missing. Ensure you run 'agent sync init' to pull latest ADRs and Rules.[/yellow]")
            return
            
        logger.debug("Notion sync state is present: %s", self.state)

    def pull(self, force: bool = False, artifact_id: Optional[str] = None, artifact_type: Optional[str] = None, silent: bool = False):
        """Pulls content from Notion to local cache."""
        if not self.client:
            return
        # 1. Stories
        if not artifact_type or artifact_type.lower() == "story":
            self._pull_category("Stories", config.stories_dir, "Stories", force, artifact_id, silent)
        
        # 2. Plans
        if not artifact_type or artifact_type.lower() == "plan":
            self._pull_category("Plans", config.plans_dir, "Plans", force, artifact_id, silent)
        
        # 3. ADRs
        if not artifact_type or artifact_type.lower() == "adr":
            self._pull_category("ADRs", config.adrs_dir, "ADRs", force, artifact_id, silent)

    def push(self, force: bool = False, artifact_id: Optional[str] = None, artifact_type: Optional[str] = None, silent: bool = False):
        """Pushes local content to Notion."""
        if not self.client:
            return
        # 1. Stories
        if not artifact_type or artifact_type.lower() == "story":
            self._push_category("Stories", config.stories_dir, "Stories", force, artifact_id, silent)
        
        # 2. Plans
        if not artifact_type or artifact_type.lower() == "plan":
            self._push_category("Plans", config.plans_dir, "Plans", force, artifact_id, silent)
        
        # 3. ADRs
        if not artifact_type or artifact_type.lower() == "adr":
            self._push_category("ADRs", config.adrs_dir, "ADRs", force, artifact_id, silent)

    # --- Pull Implementation ---

    def _pull_category(self, db_key: str, base_dir: Path, category_name: str, force: bool, artifact_id: Optional[str] = None, silent: bool = False):
        db_id = self.state.get(db_key)
        
        # Helper to retry after init
        def _try_init():
             if silent:
                 return None
             if Confirm.ask(f"[bold yellow]Notion Database for {category_name} is missing. Run 'agent sync init' to discover existing databases or create new ones?[/bold yellow]"):
                from agent.sync.bootstrap import NotionBootstrap
                NotionBootstrap().run()
                self.state = self._load_state()
                return self.state.get(db_key)
             return None

        if not db_id:
            if not silent:
                logger.warning(f"Database ID for {db_key} not found.")
            db_id = _try_init()
            if not db_id:
                if not silent:
                    logger.warning("Skipping pull.")
                return

        logger.info(f"Querying {category_name} from Notion...")
        
        # Construct Filter
        query_filter = None
        if artifact_id:
            query_filter = {
                "property": "ID",
                "rich_text": {
                    "equals": artifact_id
                }
            }
            
        try:
            pages = self.client.query_database(db_id, filter=query_filter)
        except Exception as e:
            if "object_not_found" in str(e) or "404" in str(e):
                logger.error(f"Database {db_key} not found (404).")
                db_id = _try_init()
                if db_id:
                     pages = self.client.query_database(db_id, filter=query_filter)
                else:
                     return
            else:
                raise e
        
        count = 0
        updated = 0
        skipped = 0
        
        # Pre-process to detect duplicate IDs
        pages_by_id = {}
        duplicates = set()
        
        for page in pages:
            props = page["properties"]
            id_prop = props.get("ID", {}).get("rich_text", [])
            if not id_prop: continue
            
            art_id = id_prop[0]["plain_text"]
            if art_id in pages_by_id:
                duplicates.add(art_id)
                pages_by_id[art_id].append(page)
            else:
                pages_by_id[art_id] = [page]
                
        # Warn about duplicates
        for dup_id in duplicates:
            logger.error(f"Duplicate ID detected: {dup_id}. Found {len(pages_by_id[dup_id])} pages. Skipping to avoid data loss/corruption. Please resolve in Notion.")

        # Process non-duplicates
        for art_id, p_list in pages_by_id.items():
            if art_id in duplicates:
                skipped += len(p_list)
                continue
                
            page = p_list[0]
            try:
                if self._process_pull_page(page, base_dir, category_name, force):
                    updated += 1
                else:
                    skipped += 1
                count += 1
            except Exception as e:
                logger.error(f"Failed to process page {page['id']} ({art_id}): {e}")
        
        logger.info(f"Pulled {category_name}: {updated} updated, {skipped} skipped.")

    def _process_pull_page(self, page: Dict[str, Any], base_dir: Path, category_name: str, force: bool) -> bool:
        props = page["properties"]
        
        # Extract ID
        id_prop = props.get("ID", {}).get("rich_text", [])
        if not id_prop:
            return False
        
        art_id = id_prop[0]["plain_text"]
        
        # Extract Title
        title_prop = props.get("Title", {}).get("title", [])
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        
        # Extract Status
        status_prop = props.get("Status", {}).get("select")
        status = status_prop["name"] if status_prop else "DRAFT"

        # Determine Target Path
        safe_title = self._sanitize_filename(title)
        filename = f"{art_id}-{safe_title}.md"
        
        # Scope subdirectories for Stories and Plans
        if category_name in ["Stories", "Plans"]:
            scope = art_id.split("-")[0] # e.g. BACKEND
            target_dir = base_dir / scope
        else:
            target_dir = base_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Cleanup: If moved to subdir, check if it exists in root and delete
        if target_dir != base_dir:
             root_files = list(base_dir.glob(f"{art_id}-*.md"))
             for rf in root_files:
                 logger.info(f"Removing duplicate from root: {rf.name}")
                 rf.unlink()
        
        # Check for existing file with same ID (handle renaming if title changed)
        # Search patterns: {art_id}-*.md
        existing_files = list(target_dir.glob(f"{art_id}-*.md"))
        target_file = target_dir / filename
        
        for old_file in existing_files:
            if old_file.name != filename:
                logger.info(f"Renaming {old_file.name} to {filename} (Title changed)")
                old_file.unlink() # Delete old file (we will write new content to target_file)

        # Fetch Content Blocks
        blocks = self.client.retrieve_block_children(page["id"])
        markdown_body = self._blocks_to_markdown(blocks)

        # Construct File Content
        content = f"# {art_id}: {title}\n\n"
        content += f"## State\n\n{status}\n\n"
        
        # Clean up duplications in body (Notion sometimes duplicates properties as blocks)
        lines = markdown_body.splitlines()
        
        def consume_blanks(ls):
            while ls and not ls[0].strip(): ls.pop(0)

        consume_blanks(lines)
        
        # 1. Remove Title if it appears at the top
        if lines and lines[0].strip().startswith(f"# {art_id}"):
            lines.pop(0)
            consume_blanks(lines)

        # 2. Remove Status/State header if it appears at the top
        # Check using Regex to capture ## Status or ## State (case insensitive)
        if lines and re.match(r"^##\s+(Status|State)", lines[0].strip(), re.IGNORECASE):
             lines.pop(0) # Remove header
             consume_blanks(lines)
             
             # Consume everything until the next header (## ...) or end of content
             # This ensures we clear out any duplicate statuses, old comments, or junk
             # that might have accumulated in the State section of the page body.
             while lines:
                 if lines[0].strip().startswith("## "):
                     break
                 lines.pop(0)
             
             # Clean up any trailing blanks after the section removal
             consume_blanks(lines)

        markdown_body = "\n".join(lines)
        content += markdown_body
        
        # Conflict Resolution (Interactive) for PULL
        if target_file.exists() and not force:
            local_content = target_file.read_text(encoding="utf-8")
            norm_local = self._normalize_markdown(local_content)
            norm_remote = self._normalize_markdown(content)
            if norm_local != norm_remote:
                # Conflict!
                # Show diff of normalized content for debugging
                diff = difflib.ndiff([norm_local], [norm_remote])
                diff_text = "".join(list(diff))
                logger.debug(f"Normalization Diff for {art_id}:\n{diff_text}")
                
                should_overwrite = Confirm.ask(
                    f"[bold red]Conflict detected for {art_id}[/bold red]. Remote content differs from Local.\n"
                    f"Local file: {target_file}\n"
                    f"Overwrite [bold]LOCAL[/bold] file with remote content?",
                    default=False
                )
                if not should_overwrite:
                    logger.info(f"Skipping {art_id} (User chose to keep local).")
                    return False

        # Write
        if target_file.exists() and not force:
             # Check if we should preserve local status
             # Logic: If content body matches (implicit here as we are about to write),
             # but statuses differ, we should keep the local status to avoid reverting it.
             # Note: We already did conflict detection above. If we are here, it means
             # either no conflict (bodies match) or user chose to overwrite local.
             # Wait, if user chose to overwrite, we should NOT preserve.
             # But if there was NO conflict (norm_local == norm_remote), we skipped the prompt.
             
             # We need to re-check if we skipped the prompt due to match.
             local_content = target_file.read_text(encoding="utf-8")
             norm_local = self._normalize_markdown(local_content)
             norm_remote = self._normalize_markdown(content)
             
             if norm_local == norm_remote:
                 # Content matches, check status
                 local_status = self._parse_status(local_content)
                 if local_status != status:
                     logger.info(f"[{art_id}] Content matches but status differs (Local: {local_status}, Remote: {status}). Preserving Local Status.")
                     # Patch content with local status
                     content = content.replace(f"## State\n\n{status}", f"## State\n\n{local_status}")

        # Enforce single newline at EOF
        content = content.rstrip() + "\n"
        target_file.write_text(content, encoding="utf-8")
        return True

    # --- Push Implementation ---

    def _push_category(self, db_key: str, dir_path: Path, category_name: str, force: bool, artifact_id: Optional[str] = None, silent: bool = False):
        db_id = self.state.get(db_key)
        if not db_id:
            if not silent:
                logger.warning(f"Database ID for {db_key} not found in state. Skipping push.")
            return

        artifacts = self._scan_artifacts(dir_path, category_name)
        if artifact_id:
            artifacts = [a for a in artifacts if a["id"] == artifact_id]

        if not silent:
            logger.info(f"Syncing {len(artifacts)} {category_name} to Notion...")

        updated = 0
        created = 0

        for art in artifacts:
            try:
                # Query by ID
                results = self.client.query_database(db_id, filter={
                    "property": "ID",
                    "rich_text": {
                        "equals": art["id"]
                    }
                })

                if results:
                    # Update
                    page_id = results[0]["id"]
                    if self._update_page(page_id, art, force, silent):
                        updated += 1
                else:
                    # Create
                    self._create_page(db_id, art)
                    created += 1
            except Exception as e:
                logger.error(f"Failed to sync {art['id']}: {e}")

        if not silent:
            logger.info(f"Finished pushing {category_name}: {created} created, {updated} updated.")

    def _update_page(self, page_id: str, art: Dict[str, Any], force: bool, silent: bool = False) -> bool:
        # 1. Safety Check: Verify Title matches to prevent accidental ID collision
        # We must fetch the page properties first
        remote_page = self.client.retrieve_page(page_id)
        remote_props = remote_page["properties"]
        # Extract title safeley
        remote_title_objs = remote_props.get("Title", {}).get("title", [])
        remote_title = remote_title_objs[0]["plain_text"] if remote_title_objs else ""
        
        local_title = art["title"]
        
        # Normalize whitespace for comparison
        norm_remote = re.sub(r"\W+", "", remote_title).lower()
        norm_local = re.sub(r"\W+", "", local_title).lower()
        if norm_remote != norm_local:
            if not force:
                # Only warn — since we matched by ID, this is a title update, not a collision
                if not silent:
                    logger.info(f"[{art['id']}] Title will be updated: '{remote_title}' -> '{local_title}'")
        
        # 2. Update Metadata (including Title now!)
        props = {
            "Title": { "title": [{"text": {"content": local_title}}] },
            "Status": { "select": {"name": art["status"]} },
            "ID": { "rich_text": [{"text": {"content": art["id"]}}] }
        }
        # Safe extraction of remote status
        remote_status_prop = remote_props.get("Status", {})
        remote_select = remote_status_prop.get("select") if remote_status_prop else None
        remote_status_name = remote_select.get("name") if remote_select else None

        if remote_status_name != art["status"]:
            if not silent:
                logger.info(f"[{art['id']}] Updating status: {remote_status_name} -> {art['status']}")
            
        self.client.update_page_properties(page_id, props)

        # Smart Content Sync (Diff & Overwrite)
        # 1. Fetch Remote
        remote_blocks = self.client.retrieve_block_children(page_id)
        
        should_update = False
        
        if not remote_blocks:
            should_update = True
            if not silent:
                logger.info(f"[{art['id']}] Remote is empty. Pushing content...")
        
        elif force:
            if not silent:
                logger.info(f"[{art['id']}] Force update requested.")
            should_update = True
            
        else:
            # Diff Check
            remote_md = self._blocks_to_markdown_stub(remote_blocks)
            norm_local = self._normalize_markdown(art["content"])
            norm_remote = self._normalize_markdown(remote_md)
            
            if norm_local != norm_remote:
                # Conflict Resolution (Interactive) for PUSH
                # Show diff
                diff = difflib.ndiff([norm_local], [norm_remote])
                diff_text = "".join(list(diff))
                logger.debug(f"Normalization Diff for {art['id']}:\n{diff_text}")

                if silent:
                    logger.info(f"Skipping {art['id']} (Conflict detected in silent mode).")
                    should_update = False
                else:
                    should_update = Confirm.ask(
                        f"[bold red]Conflict detected for {art['id']}[/bold red]. Local content differs from Remote.\n"
                        f"Overwrite [bold]REMOTE[/bold] Notion page with local content?",
                        default=True
                    )
                    if not should_update:
                         logger.info(f"Skipping {art['id']} (User chose to keep remote).")
            else:
                # Content matches
                pass
        
        if should_update:
            logger.info(f"[{art['id']}] Overwriting remote content...")
            # DELETE all existing blocks (in batches)
            # DELETE all existing blocks (in batches) - PARALLELIZED
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_block = {executor.submit(self.client.delete_block, block["id"]): block["id"] for block in remote_blocks}
                for future in concurrent.futures.as_completed(future_to_block):
                    block_id = future_to_block[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.warning(f"Failed to delete block {block_id}: {e}") 

            # APPEND new blocks
            new_blocks = self._markdown_to_blocks(art["content"])
            # Append in chunks of 100 (Notion limit)
            chunk_size = 100
            for i in range(0, len(new_blocks), chunk_size):
                chunk = new_blocks[i:i + chunk_size]
                self.client.append_block_children(page_id, chunk)
            return True
            
        return False

    def _create_page(self, db_id: str, art: Dict[str, Any]):
        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Title": {
                    "title": [{"text": {"content": art["title"]}}]
                },
                "ID": {
                    "rich_text": [{"text": {"content": art["id"]}}]
                },
                "Status": {
                    "select": {"name": art["status"]}
                }
            },
            "children": self._markdown_to_blocks(art["content"])
        }
        self.client._request("POST", "pages", payload)
        logger.info(f"Created new page for {art['id']}")

    # --- Helpers ---

    def _scan_artifacts(self, directory: Path, artifact_type: str) -> List[Dict[str, Any]]:
        artifacts = []
        if not directory.exists():
            return artifacts

        for file in directory.rglob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                filename = file.name
                
                # Extract ID
                match = re.match(r"^([A-Z]+-\d+)", filename)
                if match:
                    art_id = match.group(1)
                else:
                    if artifact_type == "ADR" and filename.startswith("ADR-"):
                         parts = filename.split("-")
                         if len(parts) >= 2:
                             art_id = f"{parts[0]}-{parts[1]}"
                         else: continue
                    else:
                        continue

                # Parse Content
                title = self._parse_title(content, art_id)
                status = self._parse_status(content)
                
                artifacts.append({
                    "id": art_id,
                    "title": title,
                    "status": status,
                    "content": content,
                    "path": file,
                    "type": artifact_type
                })
            except Exception as e:
                logger.warning(f"Failed to parse {file.name}: {e}")
        return artifacts

    def _parse_title(self, content: str, art_id: str) -> str:
        lines = content.splitlines()
        if not lines: return "Untitled"
        first_line = lines[0]
        # Remove markdown header
        clean = first_line.lstrip("#").strip()
        # Remove ID if present
        if clean.startswith(art_id):
             clean = clean[len(art_id):].strip().lstrip(":").strip()
        return clean

    def _parse_status(self, content: str) -> str:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^##\s+(State|Status)", line, re.IGNORECASE):
                # Search subsequent lines for status
                for j in range(i + 1, min(i + 5, len(lines))):
                    s = lines[j].strip()
                    if s: 
                        return s.upper()
        return "DRAFT"

    def _sanitize_filename(self, name: str) -> str:
        name = name.lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "-", name)
        return name[:80]

    def _blocks_to_markdown_stub(self, blocks: List[Dict[str, Any]]) -> str:
        md = []
        for block in blocks:
            btype = block["type"]
            text = ""
            if btype == "paragraph":
                text = self._get_text(block["paragraph"]["rich_text"])
            elif "heading" in btype:
                text = self._get_text(block[btype]["rich_text"])
                # Note: Notion puller added #, here we just get text for comparison normalizer
                # The normalizer strips # anyway, so this is fine.
            elif "list_item" in btype:
                text = self._get_text(block[btype]["rich_text"])
            elif "to_do" in btype:
                text = self._get_text(block["to_do"]["rich_text"])
            elif "code" in btype:
                text = self._get_text(block["code"]["rich_text"])
            
            if text: md.append(text)
        return "\n".join(md)

    def _get_text(self, rich_text: List[Dict[str, Any]]) -> str:
        return "".join([t["plain_text"] for t in rich_text])

    def _normalize_markdown(self, content: str) -> str:
        STATUS_VALUES = {"DRAFT", "PROPOSED", "ACCEPTED", "DONE", "IN_PROGRESS", "APPROVED", "REVIEW", "REJECTED", "COMMITTED"}
        lines = content.splitlines()
        filtered = []
        skip_until_next_header = False
        for line in lines:
            stripped = line.strip()
            # Strip markdown heading markers for comparison
            clean = stripped.lstrip("#").strip()

            # Skip title lines (with or without # prefix): e.g. "# ADR-001: Foo" or "ADR-001: Foo"
            if re.match(r"^[A-Z]+-\d+\s*:", clean):
                continue

            # Skip State/Status heading lines (with or without ## prefix)
            if re.match(r"^(State|Status)\s*$", clean, re.IGNORECASE):
                skip_until_next_header = True
                continue

            # Skip status value lines (e.g. "DRAFT", "ACCEPTED")
            if stripped.upper() in STATUS_VALUES:
                continue

            # If we're inside a State/Status section, skip until next heading
            if skip_until_next_header:
                if stripped.startswith("#") or re.match(r"^[A-Z][a-z]", stripped):
                    # Reached next heading — stop skipping, but process this line
                    skip_until_next_header = False
                elif not stripped:
                    continue
                else:
                    continue

            if not stripped:
                continue

            # Normalize Unicode to NFC to avoid false positives (e.g. café vs cafe\u0301)
            line = unicodedata.normalize("NFC", line)
            filtered.append(re.sub(r"\W+", "", line).lower())
        return "".join(filtered)

    def _blocks_to_markdown(self, blocks: List[Dict[str, Any]]) -> str:
        # Same as pull_from_notion.py's implementation
        md = []
        prev_type = None
        
        # Helper check for mergeable types (lists, quotes)
        # These types should be tight if consecutive and matching.
        MERGEABLE_TYPES = {"bulleted_list_item", "numbered_list_item", "to_do", "quote"}
        
        for block in blocks:
            btype = block["type"]
            current_md = ""
            
            # 1. Render content (without trailing newlines)
            if btype == "paragraph":
                current_md = self._rich_text_to_md(block["paragraph"]["rich_text"])
                if not current_md.strip():
                    continue
                
                # Fix for Notion quote spacers: paragraphs containing just ">" should be treated as quotes
                if current_md.strip() == ">":
                    btype = "quote"
            elif btype.startswith("heading_"):
                level = int(btype.split("_")[1])
                val = self._rich_text_to_md(block[btype]["rich_text"])
                current_md = f"{'#' * level} {val}"
            elif btype == "bulleted_list_item":
                val = self._rich_text_to_md(block["bulleted_list_item"]["rich_text"])
                current_md = f"- {val}"
            elif btype == "numbered_list_item":
                val = self._rich_text_to_md(block["numbered_list_item"]["rich_text"])
                current_md = f"1. {val}"
            elif btype == "to_do":
                checked = block["to_do"]["checked"]
                val = self._rich_text_to_md(block["to_do"]["rich_text"])
                mark = "x" if checked else " "
                current_md = f"- [{mark}] {val}"
            elif btype == "code":
                lang = block["code"]["language"]
                val = self._rich_text_to_md(block["code"]["rich_text"])
                current_md = f"```{lang}\n{val}\n```"
            elif btype == "quote":
                val = self._rich_text_to_md(block["quote"]["rich_text"])
                current_md = f"> {val}"
            
            # 2. Determine Spacing
            # Rule: Insert blank line BEFORE block UNLESS:
            # - It's the first block
            # - OR It is a mergeable type AND matches the previous type
            if prev_type:
                should_merge = (btype in MERGEABLE_TYPES) and (prev_type == btype)
                if not should_merge:
                    md.append("") # Adds blank line
            
            md.append(current_md)
            prev_type = btype
            
        return "\n".join(md)

    def _rich_text_to_md(self, rich_text_list: List[Dict[str, Any]]) -> str:
        text = ""
        for rt in rich_text_list:
            chunk = rt["plain_text"]
            if rt["annotations"]["bold"]:
                chunk = f"**{chunk}**"
            if rt["annotations"]["italic"]:
                chunk = f"*{chunk}*"
            if rt["annotations"]["code"]:
                chunk = f"`{chunk}`"
            if rt.get("href"):
                chunk = f"[{chunk}]({rt['href']})"
            text += chunk
        return text

    def _markdown_to_blocks(self, content: str) -> List[Dict[str, Any]]:
        blocks = []
        lines = content.splitlines()
        
        in_code_block = False
        code_lang = "plain text"
        code_content = []
        
        # Buffer for accumulating paragraph lines
        paragraph_buffer = []

        def flush_paragraph():
            if paragraph_buffer:
                text_content = " ".join(paragraph_buffer) # Markdown treats newlines as spaces in paragraphs
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": text_content}}]}
                })
                paragraph_buffer.clear()

        for line in lines:
            stripped = line.strip()
            
            # Handle Code Blocks (High Priority)
            if line.startswith("```"):
                flush_paragraph() # End previous paragraph
                if in_code_block:
                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                            "language": code_lang if code_lang else "plain text"
                        }
                    })
                    in_code_block = False
                    code_content = []
                else:
                    in_code_block = True
                    code_lang = line.strip("`").strip()
                    if not code_lang: code_lang = "plain text"
                continue
            
            if in_code_block:
                code_content.append(line) # Keep original indentation/spacing for code
                continue

            # Handle Blank Lines (Paragraph Separators)
            if not stripped:
                flush_paragraph()
                continue

            # Handle Block Types (Headers, Lists, Quotes)
            # These interrupt paragraphs
            is_special_block = False
            
            if line.startswith("# ") or line.startswith("## ") or line.startswith("### ") or \
               line.startswith("- [ ]") or line.startswith("- [x]") or \
               line.startswith("- ") or re.match(r"^\d+\.", line) or \
               line.startswith("> "):
               is_special_block = True
            
            if is_special_block:
                flush_paragraph()
                
                if line.startswith("# "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]}
                    })
                elif line.startswith("## "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:].strip()}}]}
                    })
                elif line.startswith("### "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:].strip()}}]}
                    })
                elif line.startswith("- [ ]") or line.startswith("- [x]"):
                    checked = line.startswith("- [x]")
                    text = line[5:].strip()
                    blocks.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{"type": "text", "text": {"content": text}}],
                            "checked": checked
                        }
                    })
                elif line.startswith("- "):
                     blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]}
                    })
                elif re.match(r"^\d+\.", line):
                     text = line.split(".", 1)[1].strip()
                     blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}
                    })
                elif line.startswith("> "):
                     blocks.append({
                        "object": "block",
                        "type": "quote",
                        "quote": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]}
                    })
            else:
                # Regular text line - accumulate
                # Note: We use the stripped line or original? paragraph_buffer joins with space.
                # Usually markdown ignores indentation but meaningful leading whitespace might exist.
                # For safety, let's just strip for now as typically Notion doesn't support indented paragraphs easily.
                paragraph_buffer.append(stripped)
        
        # Flush any remaining paragraph content
        flush_paragraph()
        
        return blocks
