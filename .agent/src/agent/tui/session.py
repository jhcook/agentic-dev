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

"""Conversation session persistence and token budget management (INFRA-087)."""

import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

MessageRole = Literal["user", "assistant"]


@dataclass
class Message:
    """A single message in a conversation."""

    role: MessageRole
    content: str


@dataclass
class ConversationSession:
    """A persistent conversation session."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    provider: str
    model: Optional[str] = None
    messages: List[Message] = field(default_factory=list)


class SessionStore:
    """SQLite-backed conversation session store.

    Stores conversations in ``config.cache_dir / "console.db"`` with
    file permissions ``0600`` (user-only read/write) per @Security.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            from agent.core.config import config
            db_path = config.cache_dir / "console.db"

        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # @Security: Create DB file with 0600 permissions (user-only read/write)
        # atomically before sqlite3.connect to prevent a permission race window.
        if not self._db_path.exists():
            fd = os.open(
                str(self._db_path),
                os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            os.close(fd)

        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)

        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Conversation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.commit()

    def create_session(
        self, provider: str = "", model: Optional[str] = None
    ) -> ConversationSession:
        """Create a new empty conversation session."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, provider, model) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, "New Conversation", now, now, provider, model),
        )
        self._conn.commit()
        return ConversationSession(
            id=session_id,
            title="New Conversation",
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            provider=provider,
            model=model,
            messages=[],
        )

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Retrieve a session by ID, including all messages."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None

        messages = [
            Message(role=r["role"], content=r["content"])
            for r in self._conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        ]
        return ConversationSession(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            provider=row["provider"],
            model=row["model"],
            messages=messages,
        )

    def get_latest_session(self) -> Optional[ConversationSession]:
        """Get the most recently updated session that has messages.

        Prefers sessions with actual conversation content. Falls back to
        the most recent empty session only if none have messages.
        """
        # First try: session with messages (active conversation)
        row = self._conn.execute(
            """SELECT s.id FROM sessions s
               JOIN messages m ON m.session_id = s.id
               GROUP BY s.id
               HAVING COUNT(m.id) > 0
               ORDER BY s.updated_at DESC LIMIT 1"""
        ).fetchone()
        if row:
            return self.get_session(row["id"])

        # Fallback: any session (may be empty)
        row = self._conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            return self.get_session(row["id"])
        return None

    def list_sessions(self) -> List[ConversationSession]:
        """List all sessions ordered by most recently updated."""
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        sessions = []
        for row in rows:
            msg_count = self._conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (row["id"],),
            ).fetchone()[0]
            sessions.append(
                ConversationSession(
                    id=row["id"],
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    provider=row["provider"],
                    model=row["model"],
                    messages=[],  # Don't load messages for listing
                )
            )
        return sessions

    def add_message(self, session_id: str, role: MessageRole, content: str) -> None:
        """Append a message to a session."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self._conn.commit()

    def delete_session(self, session_id: str) -> bool:
        """Hard-delete a session and all its messages."""
        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        result = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()
        return result.rowcount > 0

    def rename_session(self, session_id: str, title: str) -> None:
        """Rename a session."""
        self._conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
        )
        self._conn.commit()

    def auto_title(self, session_id: str, first_message: str) -> None:
        """Set the title from the first ~60 chars of the first user message."""
        title = first_message.strip()[:60]
        if len(first_message.strip()) > 60:
            title += "…"
        self.rename_session(session_id, title)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


class TokenBudget:
    """Manages token budget for conversation context windows.

    Prunes oldest turns FIFO while preserving the system prompt and the
    most recent turns. Logs when pruning occurs (@Observability).
    """

    def __init__(self, max_tokens: int = 8192) -> None:
        self.max_tokens = max_tokens

    def build_context(
        self,
        system_prompt: str,
        messages: List[Message],
        provider: str = "gemini",
    ) -> Tuple[str, List[Message]]:
        """Build a pruned context that fits within the token budget.

        Args:
            system_prompt: The system instruction.
            messages: Full conversation history (role/content dicts).
            provider: AI provider name for token counting.

        Returns:
            Tuple of (system_prompt, pruned_messages).

        Raises:
            ValueError: If system prompt alone exceeds the budget.
        """
        from agent.core.tokens import token_manager

        sys_tokens = token_manager.count_tokens(system_prompt, provider=provider)
        if sys_tokens >= self.max_tokens:
            raise ValueError(
                f"System prompt alone ({sys_tokens} tokens) exceeds "
                f"budget ({self.max_tokens} tokens)"
            )

        remaining = self.max_tokens - sys_tokens

        # Always keep at least the last 2 turns (user + assistant)
        min_keep = min(2, len(messages))

        # Count tokens for each message
        msg_tokens = [
            token_manager.count_tokens(m.content or "", provider=provider)
            for m in messages
        ]

        total_msg_tokens = sum(msg_tokens)

        if total_msg_tokens <= remaining:
            return system_prompt, list(messages)

        # Prune oldest messages until we fit
        pruned = list(messages)
        pruned_tokens = list(msg_tokens)
        tokens_before = total_msg_tokens
        turns_pruned = 0

        while sum(pruned_tokens) > remaining and len(pruned) > min_keep:
            pruned.pop(0)
            pruned_tokens.pop(0)
            turns_pruned += 1

        tokens_after = sum(pruned_tokens)
        if turns_pruned > 0:
            logger.info(
                "Token budget pruning applied",
                extra={
                    "turns_pruned": turns_pruned,
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "budget": self.max_tokens,
                },
            )

        return system_prompt, pruned
