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

"""Tests for agent.utils.validation_formatter module."""

import pytest

from agent.utils.validation_formatter import format_runbook_errors


class TestFormatRunbookErrors:
    """Unit tests for the format_runbook_errors function."""

    def test_empty_list_returns_empty_string(self):
        """Empty input produces empty output."""
        assert format_runbook_errors([]) == ""

    def test_single_string_error(self):
        """A single string error is formatted with numbering."""
        result = format_runbook_errors(["Missing section: Implementation Steps"])
        assert "### SCHEMA VALIDATION FAILED ###" in result
        assert "1. Missing section: Implementation Steps" in result

    def test_multiple_string_errors(self):
        """Multiple string errors are numbered sequentially."""
        errors = [
            "[steps -> 0 -> operations]: Field required",
            "[steps -> 1 -> title]: Field required",
        ]
        result = format_runbook_errors(errors)
        assert "1. [steps -> 0 -> operations]: Field required" in result
        assert "2. [steps -> 1 -> title]: Field required" in result

    def test_pydantic_error_dict(self):
        """Pydantic ErrorDict with loc/msg is formatted with path and message."""
        errors = [
            {
                "loc": ("steps", 0, "operations", 0, "ModifyBlock", "blocks"),
                "msg": "Field required",
                "type": "missing",
            }
        ]
        result = format_runbook_errors(errors)
        assert "steps -> 0 -> operations -> 0 -> ModifyBlock -> blocks" in result
        assert "Field required" in result

    def test_pydantic_error_dict_with_step_marker(self):
        """Step index is extracted as a human-friendly marker."""
        errors = [
            {
                "loc": ("steps", 2, "title"),
                "msg": "Field required",
                "type": "missing",
            }
        ]
        result = format_runbook_errors(errors)
        assert "(Step 3)" in result  # 0-indexed 2 → human-readable Step 3

    def test_mixed_string_and_dict_errors(self):
        """Both strings and dicts are handled in the same list."""
        errors = [
            "Structural error: missing header",
            {"loc": ("steps", 0, "operations"), "msg": "Value error", "type": "value_error"},
        ]
        result = format_runbook_errors(errors)
        assert "1. Structural error: missing header" in result
        assert "2." in result
        assert "Value error" in result

    def test_non_string_non_dict_fallback(self):
        """Unexpected types fall back to str() conversion."""
        errors = [42, None]
        result = format_runbook_errors(errors)
        assert "1. 42" in result
        assert "2. None" in result

    def test_dict_without_loc_or_msg(self):
        """Dict missing loc/msg keys produces graceful defaults."""
        errors = [{"type": "missing"}]
        result = format_runbook_errors(errors)
        assert "Unknown error" in result
