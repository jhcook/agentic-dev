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

"""Journey file reverse index for impact-to-journey mapping (INFRA-059)."""

import fnmatch
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

TABLE = "journey_file_index"

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    file_pattern TEXT NOT NULL,
    journey_id TEXT NOT NULL,
    journey_title TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL,
    PRIMARY KEY (file_pattern, journey_id)
)
"""


def ensure_table(conn: sqlite3.Connection) -> None:
    """Create the journey_file_index table if it doesn't exist."""
    conn.execute(CREATE_SQL)
    conn.commit()


def rebuild_index(
    conn: sqlite3.Connection,
    journeys_dir: Path,
    repo_root: Path,
) -> Dict[str, Any]:
    """Rebuild the journey file reverse index from journey YAMLs.

    Returns dict with keys: journey_count, file_glob_count,
    rebuild_duration_ms, warnings.
    """
    import yaml  # ADR-025: lazy import

    start = time.monotonic()
    warnings: List[str] = []

    ensure_table(conn)
    conn.execute(f"DELETE FROM {TABLE}")

    journey_count = 0
    file_glob_count = 0

    if not journeys_dir.exists():
        conn.commit()
        return _result(0, 0, 0.0, warnings)

    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            state = (data.get("state") or "DRAFT").upper()
            if state not in ("COMMITTED", "ACCEPTED"):
                continue

            jid = data.get("id", jfile.stem)
            title = data.get("title", "")
            files = data.get("implementation", {}).get("files", [])

            if not files:
                continue

            journey_count += 1
            now = time.time()
            pattern_count = 0

            for pattern in files:
                p = Path(pattern)
                if p.is_absolute():
                    warnings.append(f"{jid}: Absolute path rejected: '{pattern}'")
                    continue
                try:
                    resolved = (repo_root / p).resolve()
                    resolved.relative_to(repo_root.resolve())
                except ValueError:
                    warnings.append(
                        f"{jid}: Path traversal rejected: '{pattern}'"
                    )
                    continue

                conn.execute(
                    f"INSERT OR REPLACE INTO {TABLE} "
                    "(file_pattern, journey_id, journey_title, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (pattern, jid, title, now),
                )
                pattern_count += 1

            file_glob_count += pattern_count

            if pattern_count > 100:
                warnings.append(
                    f"{jid}: {pattern_count} patterns indexed "
                    "(may be overly broad)"
                )

    conn.commit()
    duration_ms = (time.monotonic() - start) * 1000

    return _result(journey_count, file_glob_count, duration_ms, warnings)


def is_stale(conn: sqlite3.Connection, journeys_dir: Path) -> bool:
    """Check if the index is stale by comparing journey YAML mtimes."""
    ensure_table(conn)
    row = conn.execute(f"SELECT MAX(updated_at) FROM {TABLE}").fetchone()
    last_updated = row[0] if row and row[0] else 0.0

    if not journeys_dir.exists():
        return False

    for scope_dir in journeys_dir.iterdir():
        if not scope_dir.is_dir():
            continue
        for jfile in scope_dir.glob("JRN-*.yaml"):
            if os.path.getmtime(jfile) > last_updated:
                return True
    return False


def get_affected_journeys(
    conn: sqlite3.Connection,
    changed_files: List[str],
    repo_root: Path,
) -> List[Dict[str, Any]]:
    """Match changed files against indexed patterns. Returns deduplicated list."""
    ensure_table(conn)

    rows = conn.execute(
        f"SELECT file_pattern, journey_id, journey_title FROM {TABLE}"
    ).fetchall()

    matches: Dict[str, Dict[str, Any]] = {}

    for pattern, jid, title in rows:
        for changed in changed_files:
            # Hybrid matching (AC-8): fnmatch first, bare filename fallback
            matched = fnmatch.fnmatch(changed, pattern)
            if not matched:
                matched = Path(changed).name == pattern
            if matched:
                if jid not in matches:
                    matches[jid] = {
                        "id": jid,
                        "title": title,
                        "matched_files": [],
                    }
                if changed not in matches[jid]["matched_files"]:
                    matches[jid]["matched_files"].append(changed)

    # Attach test files from journey YAMLs
    journeys_dir = repo_root / ".agent" / "cache" / "journeys"
    for jid, info in matches.items():
        info["tests"] = _get_journey_tests(journeys_dir, jid)

    return sorted(matches.values(), key=lambda j: j["id"])


def _get_journey_tests(journeys_dir: Path, jid: str) -> List[str]:
    """Look up implementation.tests for a journey ID."""
    import yaml  # ADR-025: lazy import

    if not journeys_dir.exists():
        return []
    for scope_dir in journeys_dir.iterdir():
        if not scope_dir.is_dir():
            continue
        for jfile in scope_dir.glob("JRN-*.yaml"):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if isinstance(data, dict) and data.get("id") == jid:
                return data.get("implementation", {}).get("tests", [])
    return []


def _result(
    journey_count: int,
    file_glob_count: int,
    rebuild_duration_ms: float,
    warnings: List[str],
) -> Dict[str, Any]:
    """Build a standard result dict."""
    return {
        "journey_count": journey_count,
        "file_glob_count": file_glob_count,
        "rebuild_duration_ms": rebuild_duration_ms,
        "warnings": warnings,
    }

class JourneyIndex:
    """Local vector database fallback for context retrieval using ChromaDB."""
    def __init__(self, persist_directory: Path | None = None):
        from agent.core.config import config
        self.persist_directory = persist_directory or (config.storage_dir / "vector_db")
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = "agentic_context"
        
        # We lazy-import these to avoid strict ai dependencies for core CLI users
        import chromadb
        from langchain_chroma import Chroma
        from agent.core.ai.service import get_embeddings_model
        
        self.chroma_client = chromadb.PersistentClient(path=str(self.persist_directory))
        self.embeddings = get_embeddings_model()
        
        self.vectorstore = Chroma(
            client=self.chroma_client,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
        )

    def build(self) -> None:
        """
        Ingest documentation and create embeddings from local rules and ADRs.
        """
        import logging
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_chroma import Chroma
        from agent.core.config import config
        from opentelemetry import trace
        
        logger = logging.getLogger(__name__)
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("vector_db.build_index"):
            # Delete existing collection to rebuild
            try:
                self.chroma_client.delete_collection(self.collection_name)
            except ValueError:
                pass # Collection doesn't exist
                
            self.vectorstore = Chroma(
                client=self.chroma_client,
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
            )

            documents = []
            metadatas = []
            ids = []
            
            # Ingest ADRs
            adrs_dir = config.repo_root / "docs" / "adrs"
            if adrs_dir.exists():
                for adr_file in adrs_dir.glob("*.md"):
                    content = adr_file.read_text(errors="ignore")
                    documents.append(content)
                    metadatas.append({"source": adr_file.name, "type": "adr"})
                    ids.append(adr_file.name)
                    
            # Ingest Global Rules
            rules_dir = config.rules_dir
            if rules_dir.exists():
                for rule_file in rules_dir.glob("*.mdc"):
                    content = rule_file.read_text(errors="ignore")
                    documents.append(content)
                    metadatas.append({"source": rule_file.name, "type": "rule"})
                    ids.append(rule_file.name)

            if not documents:
                logger.debug("No documents found for vector DB ingestion.")
                return

            splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
            chunks = splitter.create_documents(documents, metadatas=metadatas)
            
            # Extract raw text and metadata
            texts = [chunk.page_content for chunk in chunks]
            metas = [chunk.metadata for chunk in chunks]
            
            logger.debug(f"Ingesting {len(texts)} chunks into local vector DB.")
            self.vectorstore.add_texts(texts=texts, metadatas=metas)

    def search(self, query: str, k: int = 4) -> str:
        """
        Retrieve relevant context via embeddings.
        """
        import logging
        from opentelemetry import trace
        
        logger = logging.getLogger(__name__)
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("vector_db.similarity_search") as span:
            span.set_attribute("query", query)
            try:
                results = self.vectorstore.similarity_search(query, k=k)
                if not results:
                    return ""
                    
                formatted_chunks = []
                for res in results:
                    src = res.metadata.get("source", "Unknown")
                    formatted_chunks.append(f"--- Source: {src} ---\n{res.page_content}")
                    
                return "\n\n".join(formatted_chunks)
            except Exception as e:
                logger.debug(f"Error searching vector db: {e}")
                return "Local vector DB context search failed."
