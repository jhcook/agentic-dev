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

"""Unit tests for runbook_postprocess strip_empty_sr_blocks (INFRA-184 AC-1)."""

import pytest
from agent.commands.runbook_postprocess import strip_empty_sr_blocks


def test_strip_empty_sr_blocks_basic():
    """AC-1: Verify that empty SEARCH blocks are stripped and replaced with a comment."""
    content = (
        "#### [MODIFY] agent/core/utils.py\n\n"
        "```python\n"
        "<<<SEARCH\n"
        "\n"
        "===\n"
        "print('corrupted implementation')\n"
        ">>>\n"
        "```\n"
    )
    result = strip_empty_sr_blocks(content)
    # The empty <<<SEARCH block must be eliminated from the output
    assert "<<<SEARCH\n\n===" not in result


def test_strip_empty_sr_blocks_preserves_valid():
    """AC-1: Valid SEARCH blocks (with content) must be preserved."""
    content = (
        "#### [MODIFY] agent/core/utils.py\n\n"
        "```\n"
        "<<<SEARCH\n"
        "old_code()\n"
        "===\n"
        "new_code()\n"
        ">>>\n"
        "```\n"
    )
    result = strip_empty_sr_blocks(content)
    assert "old_code()" in result
    assert "new_code()" in result


def test_strip_empty_sr_blocks_no_op_on_empty_input():
    """strip_empty_sr_blocks must handle empty string without error."""
    assert strip_empty_sr_blocks("") == ""
