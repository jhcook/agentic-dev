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

"""Tests for NotionBootstrap database discovery logic."""

import pytest
from unittest.mock import patch, MagicMock

# --- Fixtures ---

PARENT_PAGE_ID = "aabbccdd11223344aabbccdd11223344"

SCHEMA = {
    "databases": {
        "Stories": {
            "title": "Stories",
            "description": "User Stories and Tasks",
            "properties": {
                "ID": {"type": "rich_text"},
                "Title": {"type": "title"},
                "Status": {
                    "type": "select",
                    "options": [{"name": "DRAFT", "color": "default"}],
                },
                "Linked Plans": {"type": "relation", "relation_target": "Plans"},
            },
        },
        "Plans": {
            "title": "Plans",
            "description": "High-level implementation plans",
            "properties": {
                "ID": {"type": "rich_text"},
                "Title": {"type": "title"},
                "Status": {
                    "type": "select",
                    "options": [{"name": "DRAFT", "color": "default"}],
                },
            },
        },
    }
}


def _make_remote_db(db_id, title, parent_page_id, properties):
    """Helper to build a mock Notion database object."""
    return {
        "id": db_id,
        "title": [{"plain_text": title}],
        "parent": {"page_id": parent_page_id},
        "properties": properties,
    }


MATCHING_STORIES_DB = _make_remote_db(
    db_id="stories-db-id-1234",
    title="Stories",
    parent_page_id=PARENT_PAGE_ID,
    properties={
        "ID": {"type": "rich_text"},
        "Title": {"type": "title"},
        "Status": {"type": "select"},
    },
)

MATCHING_PLANS_DB = _make_remote_db(
    db_id="plans-db-id-5678",
    title="Plans",
    parent_page_id=PARENT_PAGE_ID,
    properties={
        "ID": {"type": "rich_text"},
        "Title": {"type": "title"},
        "Status": {"type": "select"},
    },
)


@pytest.fixture
def mock_bootstrap():
    """Create a NotionBootstrap with mocked dependencies."""
    with patch("agent.sync.bootstrap.get_secret", return_value="fake-token"), \
         patch("agent.sync.bootstrap.config") as mock_config:

        mock_config.agent_dir = MagicMock()
        mock_config.cache_dir = MagicMock()
        mock_config.etc_dir = MagicMock()
        mock_config.load_yaml.return_value = {}
        mock_config.get_value.return_value = None

        with patch("agent.sync.bootstrap.NotionClient") as MockClient:
            mock_client_instance = MagicMock()
            MockClient.return_value = mock_client_instance

            from agent.sync.bootstrap import NotionBootstrap
            bootstrap = NotionBootstrap.__new__(NotionBootstrap)
            bootstrap.token = "fake-token"
            bootstrap.client = mock_client_instance
            bootstrap.parent_page_id = PARENT_PAGE_ID

            yield bootstrap, mock_client_instance


# --- Tests: _schema_matches ---

class TestSchemaMatches:
    def test_matching_schema(self, mock_bootstrap):
        bootstrap, _ = mock_bootstrap
        result = bootstrap._schema_matches(MATCHING_STORIES_DB, SCHEMA["databases"]["Stories"])
        assert result is True

    def test_missing_property(self, mock_bootstrap):
        bootstrap, _ = mock_bootstrap
        db = _make_remote_db("id", "Stories", PARENT_PAGE_ID, {
            "Title": {"type": "title"},
            # Missing "ID" and "Status"
        })
        result = bootstrap._schema_matches(db, SCHEMA["databases"]["Stories"])
        assert result is False

    def test_wrong_property_type(self, mock_bootstrap):
        bootstrap, _ = mock_bootstrap
        db = _make_remote_db("id", "Stories", PARENT_PAGE_ID, {
            "ID": {"type": "number"},  # Wrong type
            "Title": {"type": "title"},
            "Status": {"type": "select"},
        })
        result = bootstrap._schema_matches(db, SCHEMA["databases"]["Stories"])
        assert result is False

    def test_relations_are_skipped(self, mock_bootstrap):
        """Relations should be ignored during schema matching since they're wired in a later pass."""
        bootstrap, _ = mock_bootstrap
        # Stories schema has "Linked Plans" relation - should be skipped
        result = bootstrap._schema_matches(MATCHING_STORIES_DB, SCHEMA["databases"]["Stories"])
        assert result is True

    def test_extra_properties_are_ok(self, mock_bootstrap):
        """Remote DB having extra properties beyond our schema should still match."""
        bootstrap, _ = mock_bootstrap
        db = _make_remote_db("id", "Stories", PARENT_PAGE_ID, {
            "ID": {"type": "rich_text"},
            "Title": {"type": "title"},
            "Status": {"type": "select"},
            "ExtraField": {"type": "checkbox"},
        })
        result = bootstrap._schema_matches(db, SCHEMA["databases"]["Stories"])
        assert result is True


# --- Tests: _discover_databases ---

class TestDiscoverDatabases:
    def test_discover_finds_matching_databases(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap

        def search_side_effect(query="", filter_type="database"):
            if query == "Stories":
                return [MATCHING_STORIES_DB]
            elif query == "Plans":
                return [MATCHING_PLANS_DB]
            return []

        mock_client.search.side_effect = search_side_effect

        state = {}
        with patch("agent.sync.bootstrap.Confirm.ask", return_value=True):
            bootstrap._discover_databases(SCHEMA, state)

        assert state["Stories"] == "stories-db-id-1234"
        assert state["Plans"] == "plans-db-id-5678"

    def test_discover_skips_already_configured(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap
        state = {"Stories": "existing-id"}

        mock_client.search.return_value = [MATCHING_PLANS_DB]

        with patch("agent.sync.bootstrap.Confirm.ask", return_value=True):
            bootstrap._discover_databases(SCHEMA, state)

        # Stories should be unchanged, Plans should be discovered
        assert state["Stories"] == "existing-id"
        assert state["Plans"] == "plans-db-id-5678"
        # Search should only have been called once (for Plans)
        assert mock_client.search.call_count == 1

    def test_discover_filters_by_parent_page(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap

        wrong_parent_db = _make_remote_db(
            db_id="wrong-parent-id",
            title="Stories",
            parent_page_id="different-page-id-00000000000000",
            properties={
                "ID": {"type": "rich_text"},
                "Title": {"type": "title"},
                "Status": {"type": "select"},
            },
        )

        mock_client.search.return_value = [wrong_parent_db]

        state = {}
        with patch("agent.sync.bootstrap.Confirm.ask", return_value=True):
            bootstrap._discover_databases(SCHEMA, state)

        # Should not match because parent page doesn't match
        assert "Stories" not in state

    def test_discover_filters_by_schema(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap

        wrong_schema_db = _make_remote_db(
            db_id="wrong-schema-id",
            title="Stories",
            parent_page_id=PARENT_PAGE_ID,
            properties={
                "Name": {"type": "title"},  # Different property names
            },
        )

        mock_client.search.return_value = [wrong_schema_db]

        state = {}
        with patch("agent.sync.bootstrap.Confirm.ask", return_value=True):
            bootstrap._discover_databases(SCHEMA, state)

        assert "Stories" not in state

    def test_discover_user_declines(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap
        mock_client.search.return_value = [MATCHING_STORIES_DB]

        state = {}
        with patch("agent.sync.bootstrap.Confirm.ask", return_value=False):
            bootstrap._discover_databases(SCHEMA, state)

        assert "Stories" not in state

    def test_discover_handles_search_failure(self, mock_bootstrap):
        bootstrap, mock_client = mock_bootstrap
        mock_client.search.side_effect = Exception("Network error")

        state = {}
        # Should not raise, just log warning and move on
        bootstrap._discover_databases(SCHEMA, state)
        assert "Stories" not in state

    def test_fallback_to_creation_when_not_found(self, mock_bootstrap):
        """When discovery finds nothing, run() should create new databases."""
        bootstrap, mock_client = mock_bootstrap
        mock_client.search.return_value = []

        mock_client._request.return_value = {"id": "new-stories-id"}

        schema_file = MagicMock()
        schema_file.exists.return_value = True

        state = {}
        bootstrap._discover_databases(SCHEMA, state)

        # Nothing should be in state
        assert len(state) == 0
