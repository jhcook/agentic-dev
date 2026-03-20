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

"""Unit tests for ContextLoader story context loading (INFRA-069).

Verifies that load_context assembles the correct context dictionary
and that targeted file loading handles missing files gracefully.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.core.context import ContextLoader


# ── load_context ─────────────────────────────────────────────


class TestLoadContext:
    """Tests for ContextLoader.load_context."""

    @pytest.mark.asyncio
    async def test_load_context_returns_expected_keys(self, tmp_path):
        """load_context must return dict with all expected top-level keys."""
        loader = ContextLoader()
        # Stub internal loaders to avoid file-system dependencies
        with (
            patch.object(loader, "_load_global_rules", return_value="rules_text"),
            patch.object(loader, "_load_agents", return_value={"description": "", "checks": ""}),
            patch.object(loader, "_load_role_instructions", return_value="instructions_text"),
            patch("agent.core.context_source.load_source_tree", return_value="tree"),
            patch("agent.core.context_source.load_source_snippets", return_value="snippets"),
        ):
            result = await loader.load_context(story_id="INFRA-069", legacy_context=True)

        expected_keys = {"rules", "agents", "instructions", "adrs", "source_tree", "source_code", "context"}
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_load_context_legacy_populates_rules(self, tmp_path):
        """Legacy mode must populate rules from _load_global_rules."""
        loader = ContextLoader()
        with (
            patch.object(loader, "_load_global_rules", return_value="MY_RULES"),
            patch.object(loader, "_load_agents", return_value={"description": "", "checks": ""}),
            patch.object(loader, "_load_role_instructions", return_value=""),
            patch("agent.core.context_source.load_source_tree", return_value=""),
            patch("agent.core.context_source.load_source_snippets", return_value=""),
            patch("agent.core.context_docs.load_adrs", return_value="adrs_text"),
        ):
            result = await loader.load_context(legacy_context=True)

        assert result["rules"] == "MY_RULES"

    @pytest.mark.asyncio
    async def test_load_context_non_legacy_leaves_rules_empty(self):
        """Non-legacy mode must leave rules/instructions/adrs empty."""
        loader = ContextLoader()
        with (
            patch("agent.core.context_source.load_source_tree", return_value=""),
            patch("agent.core.context_source.load_source_snippets", return_value=""),
        ):
            result = await loader.load_context(story_id="", legacy_context=False)

        assert result["rules"] == ""
        assert result["instructions"] == ""
        assert result["adrs"] == ""


# ── _load_targeted_context ───────────────────────────────────


class TestLoadTargetedContext:
    """Tests for ContextLoader._load_targeted_context."""

    def test_existing_file_included(self, tmp_path):
        """Backtick-prefixed paths that exist are loaded into context (Pass 1)."""
        loader = ContextLoader()
        # Replicate the real directory structure the Impact Analysis uses.
        mod_path = tmp_path / ".agent" / "src" / "agent" / "foo" / "mod.py"
        mod_path.parent.mkdir(parents=True)
        mod_path.write_text("print('hello')")

        story = (
            "## Impact Analysis\n"
            "- `.agent/src/agent/foo/mod.py` — **[MODIFY]** — update logic\n"
        )
        with patch("agent.core.context.config") as mock_config:
            mock_config.repo_root = tmp_path
            result = loader._load_targeted_context(story)

        assert "TARGETED CONTEXT: .agent/src/agent/foo/mod.py" in result
        assert "print('hello')" in result

    def test_missing_file_marked_not_found(self, tmp_path):
        """Backtick-prefixed paths that don't exist are marked as not found."""
        loader = ContextLoader()

        story = (
            "## Impact Analysis\n"
            "- `.agent/src/agent/foo/nonexistent.py` — **[NEW]** — create module\n"
        )
        with patch("agent.core.context.config") as mock_config:
            mock_config.repo_root = tmp_path
            result = loader._load_targeted_context(story)

        assert "FILE NOT FOUND" in result

    def test_large_file_truncated(self, tmp_path):
        """Files exceeding 30k chars are truncated with omission notice."""
        loader = ContextLoader()
        large_dir = tmp_path / ".agent" / "src" / "agent" / "foo"
        large_dir.mkdir(parents=True)
        large_file = large_dir / "big.py"
        large_file.write_text("x" * 40000)

        story = (
            "## Impact Analysis\n"
            "- `.agent/src/agent/foo/big.py` — **[MODIFY]**\n"
        )
        with patch("agent.core.context.config") as mock_config:
            mock_config.repo_root = tmp_path
            result = loader._load_targeted_context(story)

        assert "lines omitted" in result

    def test_bare_filenames_are_excluded(self, tmp_path):
        """Bare filenames (no directory separator) must NOT be resolved.

        This prevents the rglob-based wrong-file resolution that caused
        ``__init__.py`` to be loaded from a completely different package
        and the AI to generate SEARCH blocks that never matched.
        """
        loader = ContextLoader()
        # Even if these files exist at tmp_path root, they should not appear.
        (tmp_path / "util.py").write_text("# should not appear")
        (tmp_path / "__init__.py").write_text("# should not appear")

        story = "Make changes to util.py and __init__.py."
        with patch("agent.core.context.config") as mock_config:
            mock_config.repo_root = tmp_path
            result = loader._load_targeted_context(story)

        assert "util.py" not in result
        assert "__init__.py" not in result
