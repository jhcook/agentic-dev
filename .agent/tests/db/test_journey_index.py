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

"""Unit tests for agent.db.journey_index (INFRA-059)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agent.db.journey_index import (
    ensure_table,
    get_affected_journeys,
    is_stale,
    rebuild_index,
)


def _write_journey(
    journeys_dir: Path,
    jid: str,
    *,
    state: str = "COMMITTED",
    files: list | None = None,
    tests: list | None = None,
    title: str = "",
    scope: str = "INFRA",
) -> Path:
    """Helper to write a synthetic journey YAML."""
    scope_dir = journeys_dir / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": jid,
        "title": title or f"Journey {jid}",
        "state": state,
        "implementation": {
            "files": files or [],
            "tests": tests or [],
        },
    }
    path = scope_dir / f"{jid}-test.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


@pytest.fixture
def db():
    """In-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    ensure_table(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Fake repo root with journeys dir."""
    jdir = tmp_path / ".agent" / "cache" / "journeys"
    jdir.mkdir(parents=True)
    return tmp_path


class TestRebuildIndex:
    def test_basic_rebuild(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(journeys_dir, "JRN-001", files=["src/agent/**/*.py"])

        result = rebuild_index(db, journeys_dir, repo)

        assert result["journey_count"] == 1
        assert result["file_glob_count"] == 1
        assert result["rebuild_duration_ms"] >= 0
        assert result["warnings"] == []

        rows = db.execute("SELECT * FROM journey_file_index").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "src/agent/**/*.py"
        assert rows[0][1] == "JRN-001"

    def test_draft_journeys_excluded(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(journeys_dir, "JRN-002", state="DRAFT", files=["foo.py"])

        result = rebuild_index(db, journeys_dir, repo)
        assert result["journey_count"] == 0
        assert result["file_glob_count"] == 0

    def test_empty_files_list(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(journeys_dir, "JRN-003", files=[])

        result = rebuild_index(db, journeys_dir, repo)
        assert result["journey_count"] == 0

    def test_path_traversal_rejected(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir, "JRN-004", files=["../../etc/passwd"]
        )

        result = rebuild_index(db, journeys_dir, repo)
        assert len(result["warnings"]) == 1
        assert "traversal" in result["warnings"][0].lower()

    def test_absolute_path_rejected(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(journeys_dir, "JRN-005", files=["/etc/passwd"])

        result = rebuild_index(db, journeys_dir, repo)
        assert len(result["warnings"]) == 1
        assert "Absolute" in result["warnings"][0]

    def test_missing_journeys_dir(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        result = rebuild_index(db, missing, tmp_path)
        assert result["journey_count"] == 0

    def test_multiple_patterns(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir,
            "JRN-006",
            files=["src/a.py", "src/b.py", "src/c.py"],
        )

        result = rebuild_index(db, journeys_dir, repo)
        assert result["file_glob_count"] == 3


class TestIsStale:
    def test_empty_index_is_not_stale(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        # No journeys written, so no files to compare
        assert not is_stale(db, journeys_dir)

    def test_new_journey_triggers_staleness(
        self, db: sqlite3.Connection, repo: Path
    ) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        rebuild_index(db, journeys_dir, repo)

        # Write a new journey AFTER the index was built
        _write_journey(journeys_dir, "JRN-010", files=["new.py"])

        assert is_stale(db, journeys_dir)


class TestGetAffectedJourneys:
    def test_glob_match(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir,
            "JRN-020",
            files=["src/agent/**/*.py"],
            tests=["tests/test_agent.py"],
            title="Agent Core",
        )
        rebuild_index(db, journeys_dir, repo)

        affected = get_affected_journeys(
            db, ["src/agent/commands/check.py"], repo
        )
        assert len(affected) == 1
        assert affected[0]["id"] == "JRN-020"
        assert "src/agent/commands/check.py" in affected[0]["matched_files"]
        assert "tests/test_agent.py" in affected[0]["tests"]

    def test_bare_filename_fallback(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir, "JRN-021", files=["check.py"], title="Check"
        )
        rebuild_index(db, journeys_dir, repo)

        affected = get_affected_journeys(
            db, ["src/agent/commands/check.py"], repo
        )
        assert len(affected) == 1
        assert affected[0]["id"] == "JRN-021"

    def test_no_match(self, db: sqlite3.Connection, repo: Path) -> None:
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir, "JRN-022", files=["src/mobile/**/*.ts"]
        )
        rebuild_index(db, journeys_dir, repo)

        affected = get_affected_journeys(
            db, ["src/agent/commands/check.py"], repo
        )
        assert affected == []

    def test_deduplication(self, db: sqlite3.Connection, repo: Path) -> None:
        """Overlapping globs should not duplicate journey entries."""
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir,
            "JRN-023",
            files=["src/**/*.py", "src/agent/**/*.py"],
        )
        rebuild_index(db, journeys_dir, repo)

        affected = get_affected_journeys(
            db, ["src/agent/main.py"], repo
        )
        assert len(affected) == 1  # Deduplicated by journey ID

    def test_ungoverned_file(self, db: sqlite3.Connection, repo: Path) -> None:
        """Files not matching any journey pattern are not in results."""
        journeys_dir = repo / ".agent" / "cache" / "journeys"
        _write_journey(
            journeys_dir, "JRN-024", files=["src/agent/**/*.py"]
        )
        rebuild_index(db, journeys_dir, repo)

        affected = get_affected_journeys(
            db, ["README.md"], repo
        )
        assert affected == []


class TestJourneyIndexVectorDB:
    @patch("agent.core.config.config")
    @patch("agent.core.ai.service.get_embeddings_model")
    def test_build_and_search(self, mock_get_embeddings, mock_config, tmp_path: Path):
        """Test that the local vector DB can ingest rules/ADRs and retrieve them via semantic search."""
        from langchain_core.embeddings import FakeEmbeddings
        mock_get_embeddings.return_value = FakeEmbeddings(size=384)
        mock_config.repo_root = tmp_path
        
        # Setup fake rules and adrs
        rules_dir = tmp_path / ".agent" / "rules"
        rules_dir.mkdir(parents=True)
        mock_config.rules_dir = rules_dir
        (rules_dir / "001-test.mdc").write_text("Rule 1: Always check for stubs.")
        
        adrs_dir = tmp_path / "docs" / "adrs"
        adrs_dir.mkdir(parents=True)
        (adrs_dir / "ADR-001-vector.md").write_text("# Title\nADR on vector fallback.")
        
        from agent.db.journey_index import JourneyIndex
        
        # Initialize against temp path
        idx = JourneyIndex(persist_directory=tmp_path / "index")
        
        # Build
        idx.build()
        
        # Test Search (requires sentence-transformers or mock)
        results_str = idx.search("stub", k=2)
        
        assert results_str != "", "Expected search to return at least one result."
        assert "stubs" in results_str, "Expected result to contain context about stubs"
        assert "001-test.mdc" in results_str
