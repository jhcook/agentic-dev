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

"""Tests for the tri-state summary panel from format_implementation_summary (INFRA-173).

Validates the banner logic introduced in INFRA-173:
- SUCCESS: no rejections, no warnings.
- SUCCESS WITH WARNINGS: files written with doc gaps.
- INCOMPLETE IMPLEMENTATION: one or more files rejected.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from rich.panel import Panel
from agent.utils.validation_formatter import format_implementation_summary


def test_engine_summary_success_with_warnings() -> None:
    """Verify that the banner shows SUCCESS WITH WARNINGS when warned_files is populated.

    Covers Scenario 3: banner must distinguish warnings from hard failures.
    """
    panel = format_implementation_summary(
        applied_files=["test_auth.py", "utils.py"],
        warned_files={"utils.py": ["missing function docstring"]},
        rejected_files=[],
    )
    assert isinstance(panel, Panel)
    assert "SUCCESS WITH WARNINGS" in str(panel.title)


def test_engine_summary_incomplete_implementation() -> None:
    """Verify that INCOMPLETE IMPLEMENTATION triggers when rejected_files is non-empty."""
    panel = format_implementation_summary(
        applied_files=[],
        warned_files={},
        rejected_files=["broken_file.py"],
    )
    assert isinstance(panel, Panel)
    assert "INCOMPLETE" in str(panel.title)


def test_engine_summary_clean_success() -> None:
    """Verify that plain SUCCESS renders when no warnings or rejections exist."""
    panel = format_implementation_summary(
        applied_files=["auth.py"],
        warned_files={},
        rejected_files=[],
    )
    assert isinstance(panel, Panel)
    assert "SUCCESS" in str(panel.title)
    assert "INCOMPLETE" not in str(panel.title)
    assert "WARNINGS" not in str(panel.title)


def test_regression_rejected_files_not_in_success() -> None:
    """Ensure syntax-error rejections never produce a SUCCESS banner."""
    panel = format_implementation_summary(
        applied_files=[],
        warned_files={},
        rejected_files=["invalid.py"],
    )
    assert "INCOMPLETE" in str(panel.title)
