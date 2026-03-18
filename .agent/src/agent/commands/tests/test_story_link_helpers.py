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

"""Unit tests for INFRA-158 story link back-population helpers.

Tests for:
- extract_adr_refs
- extract_journey_refs
- merge_story_links (happy path, idempotency, no-op, unwritable file)
"""

import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.commands.utils import (
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
)


# ---------------------------------------------------------------------------
# extract_adr_refs
# ---------------------------------------------------------------------------

class TestExtractAdrRefs:
    """Unit tests for extract_adr_refs."""

    def test_single_ref(self):
        """Extracts a single ADR reference from text."""
        text = "This runbook follows ADR-041 for decomposition standards."
        assert extract_adr_refs(text) == {"ADR-041"}

    def test_multiple_refs_deduplicated(self):
        """Deduplicates repeated ADR references."""
        text = "See ADR-025 and ADR-041. Also ADR-025 again."
        result = extract_adr_refs(text)
        assert result == {"ADR-025", "ADR-041"}

    def test_no_refs(self):
        """Returns empty set when no ADR references are present."""
        assert extract_adr_refs("No architectural decisions referenced here.") == set()

    def test_ignores_partial_matches(self):
        """Does not match strings that are not proper ADR-NNN tokens."""
        # 'SADR-001' should not match
        text = "SADR-001 is not an ADR reference."
        assert extract_adr_refs(text) == set()

    def test_multi_digit_adr(self):
        """Handles ADR IDs with multiple digits."""
        text = "References ADR-100 and ADR-999."
        assert extract_adr_refs(text) == {"ADR-100", "ADR-999"}


# ---------------------------------------------------------------------------
# extract_journey_refs
# ---------------------------------------------------------------------------

class TestExtractJourneyRefs:
    """Unit tests for extract_journey_refs."""

    def test_single_ref(self):
        """Extracts a single Journey reference from text."""
        text = "This touches the workflow described in JRN-057."
        assert extract_journey_refs(text) == {"JRN-057"}

    def test_multiple_refs_deduplicated(self):
        """Deduplicates repeated Journey references."""
        text = "JRN-057 and JRN-001. JRN-057 is mentioned again."
        result = extract_journey_refs(text)
        assert result == {"JRN-057", "JRN-001"}

    def test_no_refs(self):
        """Returns empty set when no Journey references are present."""
        assert extract_journey_refs("No journeys here.") == set()

    def test_ignores_partial_matches(self):
        """Does not match strings that are not proper JRN-NNN tokens."""
        text = "XJRN-001 and JRN- are not valid."
        assert extract_journey_refs(text) == set()


# ---------------------------------------------------------------------------
# merge_story_links
# ---------------------------------------------------------------------------

STORY_TEMPLATE = """\
# TEST-001: A Test Story

## Linked ADRs

- None

## Linked Journeys

- None

## Copyright

Copyright 2026 Justin Cook
"""

STORY_WITH_EXISTING_ADR = """\
# TEST-001: A Test Story

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- None

## Copyright

Copyright 2026 Justin Cook
"""


class TestMergeStoryLinks:
    """Unit tests for merge_story_links."""

    def _make_adr_dir(self, tmp_path: Path, adr_id: str, title: str) -> Path:
        """Create a minimal ADR file in a temporary adrs directory."""
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir(exist_ok=True)
        slug = adr_id.lower().replace("-", "-") + "-test"
        adr_file = adrs_dir / f"{adr_id}-{slug}.md"
        adr_file.write_text(f"# {title}\n\nSome content.\n")
        return adrs_dir

    def _make_journeys_dir(self, tmp_path: Path, jrn_id: str, name: str) -> Path:
        """Create a minimal journey YAML in a temporary journeys directory."""
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir(exist_ok=True)
        num = jrn_id.split("-")[1]
        jrn_file = journeys_dir / f"JRN-{num}-test.yaml"
        jrn_file.write_text(f"id: {jrn_id}\nname: {name}\n")
        return journeys_dir

    def test_happy_path_adr(self, tmp_path):
        """Replaces '- None' with a resolved ADR entry."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)
        adrs_dir = self._make_adr_dir(tmp_path, "ADR-041", "Module Decomposition Standards")

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = str(adrs_dir)
            mock_config.journeys_dir = None
            merge_story_links(story_file, {"ADR-041"}, set())

        result = story_file.read_text()
        assert "- ADR-041: Module Decomposition Standards" in result
        assert "- None" not in result.split("## Linked ADRs")[1].split("##")[0]

    def test_happy_path_journey(self, tmp_path):
        """Replaces '- None' with a resolved Journey entry."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)
        journeys_dir = self._make_journeys_dir(tmp_path, "JRN-057", "Impact Analysis Workflow")

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = None
            mock_config.journeys_dir = str(journeys_dir)
            merge_story_links(story_file, set(), {"JRN-057"})

        result = story_file.read_text()
        assert "- JRN-057: Impact Analysis Workflow" in result

    def test_idempotent_adr(self, tmp_path):
        """Re-running does not add a duplicate ADR entry."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_WITH_EXISTING_ADR)
        adrs_dir = self._make_adr_dir(tmp_path, "ADR-041", "Module Decomposition Standards")

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = str(adrs_dir)
            mock_config.journeys_dir = None
            merge_story_links(story_file, {"ADR-041"}, set())

        result = story_file.read_text()
        assert result.count("ADR-041") == 1

    def test_noop_when_empty_sets(self, tmp_path):
        """Story file is not modified when both ADR and Journey sets are empty."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)
        mtime_before = story_file.stat().st_mtime

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = None
            mock_config.journeys_dir = None
            merge_story_links(story_file, set(), set())

        # File should not have been touched
        assert story_file.stat().st_mtime == mtime_before

    def test_unresolvable_adr_skipped(self, tmp_path):
        """ADR reference not found on disk is skipped; section stays '- None'."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        # No ADR-099 file created

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = str(adrs_dir)
            mock_config.journeys_dir = None
            merge_story_links(story_file, {"ADR-099"}, set())

        result = story_file.read_text()
        adr_section = result.split("## Linked ADRs")[1].split("##")[0]
        assert "- None" in adr_section
        assert "ADR-099" not in adr_section

    def test_missing_adrs_dir_skips_gracefully(self, tmp_path):
        """Missing ADR directory causes all ADR refs to be skipped without error."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = str(tmp_path / "nonexistent_adrs")
            mock_config.journeys_dir = None
            # Should not raise
            merge_story_links(story_file, {"ADR-041"}, set())

        result = story_file.read_text()
        adr_section = result.split("## Linked ADRs")[1].split("##")[0]
        assert "- None" in adr_section

    def test_unwritable_story_logs_warning(self, tmp_path, caplog):
        """PermissionError on tmp file write logs a warning and does not raise."""
        story_file = tmp_path / "INFRA-001-story.md"
        story_file.write_text(STORY_TEMPLATE)
        adrs_dir = self._make_adr_dir(tmp_path, "ADR-041", "Module Decomposition Standards")

        with patch("agent.commands.utils.config") as mock_config:
            mock_config.adrs_dir = str(adrs_dir)
            mock_config.journeys_dir = None
            # Patch Path.write_text on the tmp file to simulate a PermissionError
            original_write = Path.write_text
            def _failing_write(self, *args, **kwargs):
                if self.suffix == ".tmp":
                    raise PermissionError("Read-only file system (mock)")
                return original_write(self, *args, **kwargs)

            with patch.object(Path, "write_text", _failing_write):
                with caplog.at_level(logging.WARNING, logger="agent.commands.utils"):
                    merge_story_links(story_file, {"ADR-041"}, set())
                # Must not raise — back-population is best-effort

        assert any("cannot write" in r.message for r in caplog.records)

