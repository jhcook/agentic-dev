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
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

import typer
from rich.prompt import Confirm

from agent.core.config import config
from agent.core.notion.client import NotionClient
from agent.core.secrets import get_secret

logger = logging.getLogger(__name__)

STATE_FILE = config.cache_dir / "notion_state.json"

class NotionSync:
    def __init__(self):
        self.token = get_secret("notion_token", service="agent")
        if not self.token:
            # Fallback to env var if secret not found (wraps existing logic)
            import os
            self.token = os.getenv("NOTION_TOKEN")
            
        if not self.token:
            logger.error("NOTION_TOKEN not found. Run 'agent secret login'.")
            raise typer.Exit(code=1)

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

    def pull(self, force: bool = False):
        """Pulls content from Notion to local cache."""
        # 1. Stories
        self._pull_category("Stories", config.stories_dir, "Stories", force)
        
        # 2. Plans
        self._pull_category("Plans", config.plans_dir, "Plans", force)
        
        # 3. ADRs
        self._pull_category("ADRs", config.adrs_dir, "ADRs", force)

    def push(self, force: bool = False):
        """Pushes local content to Notion."""
        # 1. Stories
        self._push_category("Stories", config.stories_dir, "Stories", force)
        
        # 2. Plans
        self._push_category("Plans", config.plans_dir, "Plans", force)
        
        # 3. ADRs
        self._push_category("ADRs", config.adrs_dir, "ADRs", force)

    # --- Pull Implementation ---

    def _pull_category(self, db_key: str, base_dir: Path, category_name: str, force: bool):
        db_id = self.state.get(db_key)
        
        # Helper to retry after init
        def _try_init():
             if Confirm.ask(f"[bold yellow]Notion Database for {category_name} is missing or not configured. Run 'agent sync init' to bootstrap?[/bold yellow]"):
                from agent.sync.bootstrap import NotionBootstrap
                NotionBootstrap().run()
                self.state = self._load_state()
                return self.state.get(db_key)
             return None

        if not db_id:
            logger.warning(f"Database ID for {db_key} not found.")
            db_id = _try_init()
            if not db_id:
                logger.warning("Skipping pull.")
                return

        logger.info(f"Querying {category_name} from Notion...")
        try:
            pages = self.client.query_database(db_id)
        except Exception as e:
            if "object_not_found" in str(e) or "404" in str(e):
                logger.error(f"Database {db_key} not found (404).")
                db_id = _try_init()
                if db_id:
                     pages = self.client.query_database(db_id)
                else:
                     return
            else:
                raise e
        
        count = 0
        updated = 0
        skipped = 0
        
        for page in pages:
            try:
                if self._process_pull_page(page, base_dir, category_name, force):
                    updated += 1
                else:
                    skipped += 1
                count += 1
            except Exception as e:
                logger.error(f"Failed to process page {page['id']}: {e}")
        
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
        
        # Scope subdirectories for Stories
        if category_name == "Stories":
            scope = art_id.split("-")[0] # e.g. BACKEND
            target_dir = base_dir / scope
        else:
            target_dir = base_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename

        # Fetch Content Blocks
        blocks = self.client.retrieve_block_children(page["id"])
        markdown_body = self._blocks_to_markdown(blocks)

        # Construct File Content
        content = f"# {art_id}: {title}\n\n"
        content += f"## Status\n{status}\n\n"
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
        target_file.write_text(content, encoding="utf-8")
        return True

    # --- Push Implementation ---

    def _push_category(self, db_key: str, dir_path: Path, category_name: str, force: bool):
        db_id = self.state.get(db_key)
        if not db_id:
            logger.warning(f"Database ID for {db_key} not found in state. Skipping push.")
            return

        artifacts = self._scan_artifacts(dir_path, category_name)
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
                    if self._update_page(page_id, art, force):
                        updated += 1
                else:
                    # Create
                    self._create_page(db_id, art)
                    created += 1
            except Exception as e:
                logger.error(f"Failed to sync {art['id']}: {e}")

        logger.info(f"Finished pushing {category_name}: {created} created, {updated} updated.")

    def _update_page(self, page_id: str, art: Dict[str, Any], force: bool) -> bool:
        # Update Metadata first (always safe?)
        props = {
            "Status": { "select": {"name": art["status"]} },
            "ID": { "rich_text": [{"text": {"content": art["id"]}}] }
        }
        self.client.update_page_properties(page_id, props)

        # Smart Content Sync (Diff & Overwrite)
        # 1. Fetch Remote
        remote_blocks = self.client.retrieve_block_children(page_id)
        
        should_update = False
        
        if not remote_blocks:
            should_update = True
            logger.info(f"[{art['id']}] Remote is empty. Pushing content...")
        
        elif force:
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
            for block in remote_blocks:
                try:
                    self.client.delete_block(block["id"])
                except Exception:
                    pass 

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
                if i + 1 < len(lines):
                    s = lines[i+1].strip()
                    if s: return s.upper()
        return "DRAFT"

    def _sanitize_filename(self, name: str) -> str:
        name = name.lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "-", name)
        return name

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
        lines = content.splitlines()
        filtered = []
        for line in lines:
            if line.startswith("# ") and ":" in line: continue 
            if line.startswith("## Status") or line.startswith("## State"): continue
            if line.upper().strip() in ["DRAFT", "PROPOSED", "ACCEPTED", "DONE", "IN_PROGRESS"]: continue 
            if not line.strip(): continue
            # Normalize Unicode to NFC to avoid false positives (e.g. café vs cafe\u0301)
            line = unicodedata.normalize("NFC", line)
            filtered.append(re.sub(r"\W+", "", line).lower())
        return "".join(filtered)

    def _blocks_to_markdown(self, blocks: List[Dict[str, Any]]) -> str:
        # Same as pull_from_notion.py's implementation
        md = []
        for block in blocks:
            btype = block["type"]
            
            if btype == "paragraph":
                content = self._rich_text_to_md(block["paragraph"]["rich_text"])
                md.append(f"{content}\n")
            elif btype.startswith("heading_"):
                level = int(btype.split("_")[1])
                val = self._rich_text_to_md(block[btype]["rich_text"])
                md.append(f"{'#' * level} {val}\n")
            elif btype == "bulleted_list_item":
                val = self._rich_text_to_md(block["bulleted_list_item"]["rich_text"])
                md.append(f"- {val}")
            elif btype == "numbered_list_item":
                 val = self._rich_text_to_md(block["numbered_list_item"]["rich_text"])
                 md.append(f"1. {val}")
            elif btype == "to_do":
                checked = block["to_do"]["checked"]
                val = self._rich_text_to_md(block["to_do"]["rich_text"])
                mark = "x" if checked else " "
                md.append(f"- [{mark}] {val}")
            elif btype == "code":
                lang = block["code"]["language"]
                val = self._rich_text_to_md(block["code"]["rich_text"])
                md.append(f"```{lang}\n{val}\n```\n")
            elif btype == "quote":
                val = self._rich_text_to_md(block["quote"]["rich_text"])
                md.append(f"> {val}\n")
            
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

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("```"):
                if in_code_block:
                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"type": "text", "text": {"content": "\\n".join(code_content)}}],
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
                code_content.append(line)
                continue

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
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]}
                })
        
        return blocks
