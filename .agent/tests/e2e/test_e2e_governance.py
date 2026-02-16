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
E2E tests for the Governance Council: role filtering, verdict aggregation,
exception suppression, and the interactive repair loop.
"""

import pytest
from unittest.mock import patch, MagicMock
from agent.core.governance import (
    _filter_relevant_roles,
    _parse_findings,
    convene_council_full,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def all_roles():
    """Return a representative set of governance roles."""
    return [
        {"name": "System Architect", "focus": "System design, ADR compliance."},
        {"name": "Quality Assurance", "focus": "Test coverage, edge cases."},
        {"name": "Security (CISO)", "focus": "Security controls, vulnerabilities."},
        {"name": "Product Owner", "focus": "User value, acceptance criteria."},
        {"name": "SRE / Observability Lead", "focus": "Logging, metrics, tracing."},
        {"name": "Tech Writer", "focus": "Documentation accuracy."},
        {"name": "Compliance (Lawyer)", "focus": "GDPR, SOC2, licensing."},
        {"name": "Mobile Lead", "focus": "React Native, Expo, offline-first."},
        {"name": "Frontend Lead", "focus": "Next.js, React Server Components."},
        {"name": "Backend Lead", "focus": "FastAPI, Python async, Pydantic."},
    ]


PYTHON_ONLY_DIFF = """\
diff --git a/agent/commands/check.py b/agent/commands/check.py
--- a/agent/commands/check.py
+++ b/agent/commands/check.py
@@ -30,7 +30,6 @@
 from agent.core.governance import convene_council_full
-from agent.core.auth.credentials import validate_credentials
 
 console = Console()
diff --git a/agent/main.py b/agent/main.py
--- a/agent/main.py
+++ b/agent/main.py
@@ -50,7 +50,1 @@
-    from dotenv import load_dotenv
-    load_dotenv()
+    # env loaded by config.py
"""

MOBILE_DIFF = """\
diff --git a/app/screens/LoginScreen.tsx b/app/screens/LoginScreen.tsx
--- a/app/screens/LoginScreen.tsx
+++ b/app/screens/LoginScreen.tsx
@@ -1,3 +1,5 @@
+import { useAuth } from '../hooks/useAuth';
 export default function LoginScreen() {
"""

WEB_DIFF = """\
diff --git a/web/pages/index.tsx b/web/pages/index.tsx
--- a/web/pages/index.tsx
+++ b/web/pages/index.tsx
@@ -1,3 +1,5 @@
+import { Metadata } from 'next';
 export default function Home() {
"""

MIXED_DIFF = """\
diff --git a/agent/core/config.py b/agent/core/config.py
--- a/agent/core/config.py
+++ b/agent/core/config.py
@@ -1,2 +1,2 @@
-OLD_VALUE = 1
+NEW_VALUE = 2
diff --git a/app/components/Button.tsx b/app/components/Button.tsx
--- a/app/components/Button.tsx
+++ b/app/components/Button.tsx
@@ -1,2 +1,2 @@
-export const Button = () => {};
+export const Button = ({label}) => <button>{label}</button>;
"""


# ===========================================================================
# Test: Role Filtering
# ===========================================================================

class TestRoleFiltering:
    """ADR-028: Platform-specific roles are skipped when no relevant files."""

    def test_python_only_diff_skips_mobile_and_frontend(self, all_roles):
        """Mobile Lead and Frontend Lead should be filtered for Python-only diffs."""
        filtered = _filter_relevant_roles(all_roles, PYTHON_ONLY_DIFF)
        names = [r["name"] for r in filtered]

        assert "Mobile Lead" not in names
        assert "Frontend Lead" not in names

    def test_python_only_diff_keeps_backend(self, all_roles):
        """Backend Lead should be included when .py files are in the diff."""
        filtered = _filter_relevant_roles(all_roles, PYTHON_ONLY_DIFF)
        names = [r["name"] for r in filtered]

        assert "Backend Lead" in names

    def test_python_only_diff_keeps_cross_cutting(self, all_roles):
        """Cross-cutting roles are always included regardless of file types."""
        filtered = _filter_relevant_roles(all_roles, PYTHON_ONLY_DIFF)
        names = [r["name"] for r in filtered]

        for role_name in ["System Architect", "Security (CISO)", "Quality Assurance",
                          "Compliance (Lawyer)", "Product Owner",
                          "SRE / Observability Lead", "Tech Writer"]:
            assert role_name in names, f"{role_name} should always be included"

    def test_mobile_diff_includes_mobile_lead(self, all_roles):
        """Mobile Lead should be included when .tsx files under app/ are changed."""
        filtered = _filter_relevant_roles(all_roles, MOBILE_DIFF)
        names = [r["name"] for r in filtered]

        assert "Mobile Lead" in names

    def test_web_diff_includes_frontend_lead(self, all_roles):
        """Frontend Lead should be included when web/ .tsx files are changed."""
        filtered = _filter_relevant_roles(all_roles, WEB_DIFF)
        names = [r["name"] for r in filtered]

        assert "Frontend Lead" in names

    def test_mixed_diff_includes_relevant_platforms(self, all_roles):
        """Both Backend Lead and Mobile Lead should match a mixed .py + .tsx diff."""
        filtered = _filter_relevant_roles(all_roles, MIXED_DIFF)
        names = [r["name"] for r in filtered]

        assert "Backend Lead" in names
        # .tsx file under app/components/ - mobile checks for .tsx
        assert "Mobile Lead" in names

    def test_empty_diff_returns_all_roles(self, all_roles):
        """An empty diff should return all roles (safe default)."""
        filtered = _filter_relevant_roles(all_roles, "")
        assert len(filtered) == len(all_roles)

    def test_dev_null_paths_ignored(self, all_roles):
        """Deleted files (--- /dev/null) should not pollute the file list."""
        diff = """\
diff --git a/agent/core/utils.py b/agent/core/utils.py
--- /dev/null
+++ b/agent/core/utils.py
@@ -0,0 +1,5 @@
+def hello():
+    pass
"""
        filtered = _filter_relevant_roles(all_roles, diff)
        names = [r["name"] for r in filtered]

        # .py file => backend included, mobile/frontend excluded
        assert "Backend Lead" in names
        assert "Mobile Lead" not in names


# ===========================================================================
# Test: Findings Parsing
# ===========================================================================

class TestFindingsParsing:

    def test_parse_pass_verdict(self):
        """A PASS verdict should be correctly extracted."""
        review = "VERDICT: PASS\nSUMMARY: All good.\nFINDINGS: None"
        parsed = _parse_findings(review)
        assert parsed["verdict"] == "PASS"
        assert "All good" in parsed["summary"]

    def test_parse_block_verdict(self):
        """A BLOCK verdict with findings should be correctly parsed."""
        review = (
            "VERDICT: BLOCK\n"
            "SUMMARY: Security issues found.\n"
            "FINDINGS:\n"
            "- eval() usage in fixer.py\n"
            "- Hardcoded secret in config\n"
            "REQUIRED_CHANGES:\n"
            "- Remove eval()\n"
            "- Rotate the secret"
        )
        parsed = _parse_findings(review)
        assert parsed["verdict"] == "BLOCK"
        assert "Security issues" in parsed["summary"]
        assert len(parsed["findings"]) > 0
        assert len(parsed["required_changes"]) > 0

    def test_parse_bold_markdown_verdict(self):
        """Verdicts wrapped in **bold** markdown should be parsed correctly."""
        review = "**VERDICT: PASS**\nSUMMARY: Looking good.\nFINDINGS: None"
        parsed = _parse_findings(review)
        assert parsed["verdict"] == "PASS"

    def test_parse_missing_verdict_defaults_pass(self):
        """If no VERDICT line is present, default to PASS."""
        review = "Everything looks fine. No issues found."
        parsed = _parse_findings(review)
        assert parsed["verdict"] == "PASS"


# ===========================================================================
# Test: Council Verdict Aggregation
# ===========================================================================

class TestCouncilVerdictAggregation:

    @patch("agent.core.governance.load_roles")
    @patch("agent.core.governance.ai_service")
    @patch("agent.core.governance.config")
    def test_all_pass_returns_pass(self, mock_config, mock_ai, mock_load_roles):
        """When all roles return PASS, overall verdict should be PASS."""
        mock_load_roles.return_value = [
            {"name": "System Architect", "focus": "Design"},
            {"name": "Security (CISO)", "focus": "Security"},
        ]
        mock_config.get_council_tools.return_value = []
        mock_config.etc_dir = MagicMock()
        mock_ai.provider = "gh"
        mock_ai.complete.return_value = (
            "VERDICT: PASS\nSUMMARY: All good.\nFINDINGS: None"
        )

        result = convene_council_full(
            story_id="TEST-001",
            story_content="Test story",
            rules_content="",
            instructions_content="",
            full_diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            adrs_content="ADR-027: Security blocklist strings are compliant.\nADR-028: Typer uses sync subprocess.",
        )

        assert result["verdict"] == "PASS"

    @patch("agent.core.governance.load_roles")
    @patch("agent.core.governance.ai_service")
    @patch("agent.core.governance.config")
    def test_one_block_returns_block(self, mock_config, mock_ai, mock_load_roles):
        """When any role returns BLOCK, overall verdict should be BLOCK."""
        mock_load_roles.return_value = [
            {"name": "System Architect", "focus": "Design"},
            {"name": "Security (CISO)", "focus": "Security"},
        ]
        mock_config.get_council_tools.return_value = []
        mock_config.etc_dir = MagicMock()
        mock_ai.provider = "gh"
        mock_ai.complete.side_effect = [
            "VERDICT: PASS\nSUMMARY: OK\nFINDINGS: None",
            "VERDICT: BLOCK\nSUMMARY: Hardcoded secret.\nFINDINGS:\n- API key in source\nREQUIRED_CHANGES:\n- Remove API key",
        ]

        result = convene_council_full(
            story_id="TEST-001",
            story_content="Test story",
            rules_content="",
            instructions_content="",
            full_diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
        )

        assert result["verdict"] == "BLOCK"

    @patch("agent.core.governance.load_roles")
    @patch("agent.core.governance.ai_service")
    @patch("agent.core.governance.config")
    def test_consultative_mode_ignores_block(self, mock_config, mock_ai, mock_load_roles):
        """In consultative mode, BLOCK verdicts from AI should NOT trigger overall BLOCK."""
        mock_load_roles.return_value = [
            {"name": "System Architect", "focus": "Design"},
        ]
        mock_config.get_council_tools.return_value = []
        mock_config.etc_dir = MagicMock()
        mock_ai.provider = "gh"
        mock_ai.complete.return_value = (
            "VERDICT: BLOCK\nSUMMARY: Issues found.\nFINDINGS:\n- Something\nREQUIRED_CHANGES:\n- Fix it"
        )

        result = convene_council_full(
            story_id="TEST-001",
            story_content="Test story",
            rules_content="",
            instructions_content="",
            full_diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            mode="consultative",
        )

        assert result["verdict"] == "PASS"


# ===========================================================================
# Test: ADR Compliance (Integration)
# ===========================================================================

class TestADRCompliance:
    """
    Verify that ADR-027 and ADR-028 summaries, when included in the
    governance context, are available to the council prompt.
    """

    @patch("agent.core.governance.load_roles")
    @patch("agent.core.governance.ai_service")
    @patch("agent.core.governance.config")
    def test_adr_content_passed_to_prompt(self, mock_config, mock_ai, mock_load_roles):
        """ADR summaries should appear in the prompt sent to each role."""
        mock_load_roles.return_value = [
            {"name": "System Architect", "focus": "Design"},
        ]
        mock_config.get_council_tools.return_value = []
        mock_config.etc_dir = MagicMock()
        mock_ai.provider = "gh"
        mock_ai.complete.return_value = (
            "VERDICT: PASS\nSUMMARY: Compliant.\nFINDINGS: None"
        )

        adr_summaries = (
            "ADR-027: Security blocklist strings are detection patterns, not invocations.\n"
            "ADR-028: Typer commands are synchronous. subprocess.run is correct."
        )

        convene_council_full(
            story_id="TEST-001",
            story_content="Test story",
            rules_content="",
            instructions_content="",
            full_diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            adrs_content=adr_summaries,
        )

        # Verify the ADR content was included in the user prompt
        call_args = mock_ai.complete.call_args
        # complete(system_prompt, user_prompt) - positional args
        assert call_args is not None, "ai_service.complete was not called"
        args, kwargs = call_args
        # user_prompt is the second positional arg
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        assert "ADR-027" in user_prompt or "blocklist" in user_prompt.lower()
