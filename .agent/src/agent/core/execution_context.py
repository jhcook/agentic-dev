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

"""
Execution context injection via ContextVar (ADR-100).

Provides a thread-safe, async-safe mechanism for passing contextual data
(e.g. session_id) into tool functions without exposing them as LLM-callable
parameters in the tool schema.

Usage (orchestrator side)::

    from agent.core.execution_context import set_session_id, reset_session_id
    token = set_session_id(self.session_id)
    # ... run session interaction ...
    reset_session_id(token)   # restore previous value

Usage (tool function side)::

    from agent.core.execution_context import get_session_id
    session_id = get_session_id()   # returns "unknown" if not set
"""

import contextvars

# ---------------------------------------------------------------------------
# session_id ContextVar
# ---------------------------------------------------------------------------
_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default="unknown"
)


def get_session_id() -> str:
    """Return the current session_id from the execution context.

    Returns ``"unknown"`` if no session has been set (e.g. in unit tests or
    tools called outside the orchestrated execution path).
    """
    return _session_id_var.get()


def set_session_id(session_id: str) -> contextvars.Token:
    """Set the session_id for the current async/thread context.

    Returns the :class:`contextvars.Token` that can be passed to
    :func:`reset_session_id` to restore the previous value.
    """
    return _session_id_var.set(session_id)


def reset_session_id(token: contextvars.Token) -> None:
    """Restore the session_id to its previous value using *token*."""
    _session_id_var.reset(token)
