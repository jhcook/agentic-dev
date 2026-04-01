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

import unittest
from unittest.mock import patch
import json
from pathlib import Path
import tempfile
import shutil
import typer
from agent.commands import check

class TestPreflightReport(unittest.TestCase):
    """
    Regression tests for Preflight Reporting (INFRA-042).
    Ensures that --report-file triggers JSON output on both success and failure.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.report_path = Path(self.test_dir) / "report.json"
        
        # Mock dependencies in check.py
        self.mock_console_patch = patch('agent.commands.check.console')
        self.mock_console = self.mock_console_patch.start()
        
        self.mock_run_patch = patch('subprocess.run')
        self.mock_run = self.mock_run_patch.start()
        self.mock_run.return_value.returncode = 0
        self.mock_run.return_value.stdout = "some_file.py"
        
        self.mock_validate_patch = patch('agent.core.check.system.validate_story')
        self.mock_validate = self.mock_validate_patch.start()
        self.mock_validate.return_value = {"passed": True, "error": None, "story_file": None}

        self.mock_analyzer_patch = patch('agent.core.dependency_analyzer.DependencyAnalyzer')
        self.mock_analyzer = self.mock_analyzer_patch.start()
        self.mock_analyzer.return_value.get_file_dependencies.return_value = set()

        self.mock_convene_patch = patch('agent.commands.check.convene_council_full')
        self.mock_convene = self.mock_convene_patch.start()
        self.mock_convene.return_value = {
            "verdict": "PASS",
            "log_file": "log.md",
            "json_report": {
                "roles": [],
                "overall_verdict": "PASS"
            }
        }

        self.mock_journey_patch = patch('agent.commands.check.validate_linked_journeys')
        self.mock_journey = self.mock_journey_patch.start()
        self.mock_journey.return_value = {"passed": True, "journey_ids": [], "error": None}
        
        # Additional mock gates
        self.mock_adr_patch = patch('agent.commands.lint.run_adr_enforcement')
        self.mock_adr = self.mock_adr_patch.start()
        self.mock_adr.return_value = True
        
        self.mock_cq_patch = patch('agent.commands.check.check_code_quality', create=True)
        self.mock_cq = self.mock_cq_patch.start()
        # Create a mock namedtuple/object for quality_result
        class MockQR:
            passed = True
            name = "Code Quality"
            details = "All good"
        self.mock_cq.return_value = MockQR()
        
        self.mock_coverage_patch = patch('agent.core.check.journeys.check_journey_coverage_gate')
        self.mock_coverage = self.mock_coverage_patch.start()
        self.mock_coverage.return_value = {"passed": True, "warnings": [], "error": None, "linked": 0, "total": 0}

        self.mock_mapping_patch = patch('agent.core.check.journeys.run_journey_impact_mapping')
        self.mock_mapping = self.mock_mapping_patch.start()
        self.mock_mapping.return_value = {}

        # Mock Notion and NotebookLM interactions
        self.mock_sync_notebooklm_patch = patch('agent.sync.notebooklm.ensure_notebooklm_sync')
        self.mock_sync_notebooklm = self.mock_sync_notebooklm_patch.start()

    def tearDown(self):
        self.mock_console_patch.stop()
        self.mock_run_patch.stop()
        self.mock_validate_patch.stop()
        self.mock_analyzer_patch.stop()
        self.mock_convene_patch.stop()
        self.mock_journey_patch.stop()
        self.mock_adr_patch.stop()
        self.mock_cq_patch.stop()
        self.mock_coverage_patch.stop()
        self.mock_mapping_patch.stop()
        self.mock_sync_notebooklm_patch.stop()
        shutil.rmtree(self.test_dir)

    def test_report_generated_on_success(self):
        """
        Verify report.json is created when preflight checks pass.
        """
        try:
            check.preflight(
                story_id="TEST-001",
                offline=True,
                report_file=self.report_path,
                skip_tests=True,
                base=None,
                provider=None,
                ignore_tests=False,
                interactive=False,
                autoheal=False,
                budget=3
            )
        except typer.Exit:
            pass # Typer always exits

        self.assertTrue(self.report_path.exists(), "Report file should exist on success")
        data = json.loads(self.report_path.read_text())
        self.assertEqual(data["overall_verdict"], "PASS")

    def test_report_generated_on_governance_block(self):
        """
        Verify report.json is created when governance blocks the preflight.
        """
        # Mock governance block
        self.mock_convene.return_value = {
            "verdict": "BLOCK",
            "log_file": "log.md",
            "json_report": {
                "roles": [{"name": "Security", "verdict": "BLOCK", "findings": ["Bad implementation"]}],
                "overall_verdict": "BLOCK"
            }
        }

        try:
            check.preflight(
                story_id="TEST-002",
                offline=False,
                report_file=self.report_path,
                skip_tests=True,
                base=None,
                provider=None,
                ignore_tests=False,
                interactive=False,
                autoheal=False,
                budget=3
            )
        except typer.Exit as e:
            self.assertEqual(e.exit_code, 1)

        self.assertTrue(self.report_path.exists(), "Report file should exist on governance block")
        data = json.loads(self.report_path.read_text())
        self.assertEqual(data["overall_verdict"], "BLOCK")
        self.assertEqual(data["roles"][0]["verdict"], "BLOCK")

if __name__ == '__main__':
    unittest.main()
