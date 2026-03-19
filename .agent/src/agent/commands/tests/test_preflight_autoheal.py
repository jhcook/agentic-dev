# Copyright 2024-2026 Justin Cook
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
Unit tests for preflight autoheal logic (INFRA-163).

Covers:
- PreflightHealer: budget enforcement, shared budget across roles, staged-change application.
- TestHealer: budget enforcement, failing-file extraction, PII scrubbing, self-protection.
"""

from unittest.mock import MagicMock, patch
from agent.core.preflight.healer import PreflightHealer, _PROTECTED_RE
from agent.core.preflight.test_healer import TestHealer, _FILE_RE


# ---------------------------------------------------------------------------
# PreflightHealer
# ---------------------------------------------------------------------------

def test_governance_healer_budget_enforced():
    """Healer refuses to attempt after budget is exhausted."""
    healer = PreflightHealer(budget=1)
    healer._attempts = 1  # simulate exhausted
    result = healer.heal("Security", "finding", [], "diff")
    assert result is False


def test_governance_healer_budget_stored():
    healer = PreflightHealer(budget=5)
    assert healer.budget == 5
    assert healer._attempts == 0


def test_governance_healer_empty_ai_response():
    """Empty AI response returns False without crashing."""
    healer = PreflightHealer(budget=3)
    with patch("agent.core.ai.service.ai_service.complete", return_value=""):
        result = healer.heal("Security", "finding", ["fix this"], "diff")
    assert result is False


def test_governance_healer_no_modify_blocks_parsed():
    """AI response with no [MODIFY] blocks returns False."""
    healer = PreflightHealer(budget=3)
    with patch("agent.core.ai.service.ai_service.complete", return_value="Some prose with no modify blocks."):
        result = healer.heal("Security", "finding", ["fix this"], "diff")
    assert result is False


def test_governance_healer_applies_edits(tmp_path, monkeypatch):
    """Parsed [MODIFY] blocks are written to disk and staged."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "agent" / "core" / "utils.py"
    target.parent.mkdir(parents=True)
    target.write_text("# old content\n")

    rel_path = target.relative_to(tmp_path)
    response = (
        f"#### [MODIFY] {rel_path}\n"
        "```python\n"
        "# fixed content\n"
        "```\n"
    )
    healer = PreflightHealer(budget=3)
    with patch("agent.core.ai.service.ai_service.complete", return_value=response), \
         patch("agent.core.preflight.healer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = healer.heal("Security", "finding", ["fix this"], "diff")

    assert result is True
    assert "fixed content" in target.read_text()


def test_governance_healer_required_changes_list():
    """required_changes as a list is joined into bullet string for the prompt."""
    healer = PreflightHealer(budget=3)
    captured = []

    def fake_complete(system_prompt, user_prompt):
        captured.append(user_prompt)
        return ""

    with patch("agent.core.ai.service.ai_service.complete", side_effect=fake_complete):
        healer.heal("Security", "finding", ["Add logging", "Remove secret"], "diff")

    assert captured
    assert "- Add logging" in captured[0]
    assert "- Remove secret" in captured[0]


def test_governance_healer_skips_protected_files(tmp_path, monkeypatch):
    """Healer silently skips healer.py and test_healer.py — no self-modification."""
    monkeypatch.chdir(tmp_path)
    response = (
        "#### [MODIFY] agent/core/preflight/healer.py\n"
        "```python\n"
        "# malicious overwrite\n"
        "```\n"
    )
    healer = PreflightHealer(budget=3)
    with patch("agent.core.ai.service.ai_service.complete", return_value=response), \
         patch("agent.core.preflight.healer.subprocess.run"):
        result = healer.heal("Security", "finding", ["fix this"], "diff")
    assert result is False


# ---------------------------------------------------------------------------
# _PROTECTED_RE
# ---------------------------------------------------------------------------

def test_protected_re_matches_healer():
    assert _PROTECTED_RE.search("agent/core/preflight/healer.py")
    assert _PROTECTED_RE.search("agent/core/preflight/test_healer.py")


def test_protected_re_does_not_match_other_files():
    assert not _PROTECTED_RE.search("agent/core/utils.py")
    assert not _PROTECTED_RE.search("agent/commands/check.py")


# ---------------------------------------------------------------------------
# TestHealer
# ---------------------------------------------------------------------------

def test_test_healer_budget_stored():
    healer = TestHealer(budget=2)
    assert healer.budget == 2
    assert healer._attempts == 0


def test_test_healer_budget_enforced():
    """Healer refuses after budget exhausted."""
    healer = TestHealer(budget=1)
    healer._attempts = 1
    result = healer.heal_failure("traceback text", ["pytest", "tests/"], None)
    assert result is False


def test_file_regex_matches_quoted_path():
    """_FILE_RE extracts paths from quoted File '...' traceback lines."""
    tb = '  File "agent/core/utils.py", line 45, in scrub_sensitive_data\n    AssertionError'
    matches = _FILE_RE.findall(tb)
    paths = [q or b for q, b in matches]
    assert "agent/core/utils.py" in paths


def test_file_regex_matches_bare_path():
    """_FILE_RE extracts bare .agent/src/ paths."""
    tb = ".agent/src/agent/core/utils.py:45: AssertionError"
    matches = _FILE_RE.findall(tb)
    paths = [q or b for q, b in matches]
    assert ".agent/src/agent/core/utils.py" in paths


def test_test_healer_pii_scrubbed_before_ai():
    """scrub_sensitive_data is called before AI receives the traceback."""
    healer = TestHealer(budget=3)
    with patch("agent.core.preflight.test_healer.scrub_sensitive_data", return_value="[SCRUBBED]") as mock_scrub, \
         patch("agent.core.ai.service.ai_service.complete", return_value=None):
        tb = 'File "agent/core/utils.py", line 1\npassword=supersecret123'
        healer.heal_failure(tb, ["pytest", "."], None)
    mock_scrub.assert_called_once_with(tb)


def test_test_healer_skips_test_files():
    """TestHealer should not attempt to fix test files."""
    healer = TestHealer(budget=3)
    tb = 'File "agent/core/tests/test_utils.py", line 12\n  AssertionError'
    files = healer._extract_failing_files(tb)
    assert not any("test_" in f for f in files)


def test_test_healer_skips_protected_files():
    """TestHealer must never include healer.py or test_healer.py as targets."""
    healer = TestHealer(budget=3)
    tb = (
        'File "agent/core/preflight/healer.py", line 95\n'
        '  TypeError: expected str\n'
        'File "agent/core/preflight/test_healer.py", line 72\n'
        '  AttributeError\n'
    )
    files = healer._extract_failing_files(tb)
    assert files == [], f"Expected no files, got: {files}"
