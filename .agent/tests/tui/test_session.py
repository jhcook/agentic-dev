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

"""Tests for SessionStore and TokenBudget (INFRA-087)."""

import os

import pytest

from agent.tui.session import Message, SessionStore, TokenBudget


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_console.db"


@pytest.fixture
def store(tmp_db):
    """Create a SessionStore with a temp database."""
    s = SessionStore(db_path=tmp_db)
    yield s
    s.close()


class TestSessionStore:
    """Tests for SessionStore CRUD operations."""

    def test_create_session(self, store):
        session = store.create_session(provider="gemini")
        assert session.id
        assert session.title == "New Conversation"
        assert session.provider == "gemini"
        assert session.messages == []

    def test_get_session(self, store):
        created = store.create_session(provider="vertex")
        retrieved = store.get_session(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.provider == "vertex"

    def test_get_session_not_found(self, store):
        assert store.get_session("nonexistent-id") is None

    def test_list_sessions(self, store):
        store.create_session(provider="a")
        store.create_session(provider="b")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_delete_session(self, store):
        session = store.create_session()
        store.add_message(session.id, "user", "hello")
        assert store.delete_session(session.id)
        assert store.get_session(session.id) is None

    def test_delete_nonexistent(self, store):
        assert not store.delete_session("no-such-id")

    def test_rename_session(self, store):
        session = store.create_session()
        store.rename_session(session.id, "My Chat")
        retrieved = store.get_session(session.id)
        assert retrieved.title == "My Chat"

    def test_auto_title_short(self, store):
        session = store.create_session()
        store.auto_title(session.id, "Hello world")
        retrieved = store.get_session(session.id)
        assert retrieved.title == "Hello world"

    def test_auto_title_long(self, store):
        session = store.create_session()
        long_msg = "a" * 100
        store.auto_title(session.id, long_msg)
        retrieved = store.get_session(session.id)
        assert len(retrieved.title) == 61  # 60 + ellipsis
        assert retrieved.title.endswith("…")

    def test_add_and_retrieve_messages(self, store):
        session = store.create_session()
        store.add_message(session.id, "user", "Hello")
        store.add_message(session.id, "assistant", "Hi there!")
        retrieved = store.get_session(session.id)
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0] == Message(role="user", content="Hello")
        assert retrieved.messages[1] == Message(role="assistant", content="Hi there!")

    def test_get_latest_session(self, store):
        s1 = store.create_session(provider="a")
        s2 = store.create_session(provider="b")
        store.add_message(s2.id, "user", "latest")
        latest = store.get_latest_session()
        assert latest.id == s2.id

    def test_get_latest_session_prefers_messages(self, store):
        """@QA: get_latest_session should prefer sessions with messages
        over empty sessions, even if the empty one is more recent."""
        old = store.create_session(provider="gemini")
        store.add_message(old.id, "user", "hello")
        store.add_message(old.id, "assistant", "hi")
        # Create a newer empty session (simulates blank-screen bug)
        _empty = store.create_session(provider="gemini")
        # Should return the older session that has messages
        latest = store.get_latest_session()
        assert latest.id == old.id
        assert len(latest.messages) == 2

    def test_get_latest_session_fallback_to_empty(self, store):
        """@QA: When no sessions have messages, fall back to most recent."""
        s1 = store.create_session(provider="a")
        s2 = store.create_session(provider="b")
        latest = store.get_latest_session()
        assert latest.id == s2.id
        assert len(latest.messages) == 0

    def test_get_latest_session_multiple_with_messages(self, store):
        """@QA: When multiple sessions have messages, return the most recent."""
        s1 = store.create_session(provider="a")
        store.add_message(s1.id, "user", "older")
        s2 = store.create_session(provider="b")
        store.add_message(s2.id, "user", "newer")
        latest = store.get_latest_session()
        assert latest.id == s2.id

    def test_get_latest_session_empty(self, store):
        assert store.get_latest_session() is None

    def test_db_file_permissions(self, tmp_db):
        """@Security: DB should be created with 0600 permissions."""
        store = SessionStore(db_path=tmp_db)
        mode = os.stat(tmp_db).st_mode & 0o777
        assert mode == 0o600, f"Expected 0600 but got {oct(mode)}"
        store.close()


class TestTokenBudget:
    """Tests for TokenBudget context pruning."""

    def test_no_pruning_needed(self):
        budget = TokenBudget(max_tokens=100000)
        system = "You are helpful."
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        sys_out, msgs_out = budget.build_context(system, messages, provider="gemini")
        assert sys_out == system
        assert len(msgs_out) == 2

    def test_fifo_pruning(self):
        budget = TokenBudget(max_tokens=100)
        system = "System."
        # Create enough messages to exceed budget
        messages = [
            Message(role="user", content="message " * 20),
            Message(role="assistant", content="response " * 20),
            Message(role="user", content="recent"),
            Message(role="assistant", content="latest"),
        ]
        _, msgs_out = budget.build_context(system, messages, provider="gemini")
        # Should have pruned older messages, keeping at least the last 2
        assert len(msgs_out) <= len(messages)
        assert len(msgs_out) >= 2
        # Last message should be preserved
        assert msgs_out[-1].content == "latest"

    def test_single_message_no_pruning(self):
        """@QA: Single message should never be pruned."""
        budget = TokenBudget(max_tokens=100000)
        system = "System."
        messages = [Message(role="user", content="Hello")]
        _, msgs_out = budget.build_context(system, messages, provider="gemini")
        assert len(msgs_out) == 1

    def test_system_prompt_exceeds_budget(self):
        """@QA: Should raise ValueError if system prompt alone exceeds budget."""
        budget = TokenBudget(max_tokens=5)
        system = "A very long system prompt that definitely exceeds five tokens"
        messages = [Message(role="user", content="Hi")]
        with pytest.raises(ValueError, match="System prompt alone"):
            budget.build_context(system, messages, provider="gemini")

    def test_exactly_at_budget(self):
        """@QA: Edge case — messages fit exactly within budget."""
        budget = TokenBudget(max_tokens=10000)
        system = "Short."
        messages = [Message(role="user", content="Hello")]
        sys_out, msgs_out = budget.build_context(system, messages, provider="gemini")
        assert len(msgs_out) == 1

    def test_empty_messages(self):
        budget = TokenBudget(max_tokens=1000)
        sys_out, msgs_out = budget.build_context("System", [], provider="gemini")
        assert msgs_out == []
