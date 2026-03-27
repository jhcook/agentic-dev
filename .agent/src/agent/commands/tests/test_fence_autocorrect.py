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

"""Tests for _ensure_modify_blocks_fenced autocorrect helper (INFRA-170)."""

import pytest

from agent.commands.runbook_generation import (
    _ensure_modify_blocks_fenced,
    _ensure_new_blocks_fenced,
)


SR_BARE = """#### [MODIFY] .agent/src/agent/commands/check.py
<<<SEARCH
def foo():
    return 1
===
def foo():
    return 2
>>>
"""

SR_FENCED = """#### [MODIFY] .agent/src/agent/commands/check.py

```python
<<<SEARCH
def foo():
    return 1
===
def foo():
    return 2
>>>
```
"""

SR_YAML_BARE = """#### [MODIFY] .agent/etc/agent.yaml
<<<SEARCH
key: old
===
key: new
>>>
"""

SR_NO_MARKERS = """#### [MODIFY] .agent/src/agent/commands/check.py

Just some prose, no S/R markers here.
"""

SR_DUNDER_BARE = r"""#### [MODIFY] .agent/src/agent/core/governance/\_\_init\_\_.py
<<<SEARCH
from agent.core.governance.roles import load_roles
===
from agent.core.governance.roles import load_roles
from agent.core.governance.complexity import get_complexity_report
>>>
"""


class TestEnsureModifyBlocksFenced:
    """Unit tests for the [MODIFY] fence autocorrect helper."""

    def test_bare_sr_gets_fenced(self):
        """A bare S/R block (no code fences) is wrapped in ```python fences."""
        result = _ensure_modify_blocks_fenced(SR_BARE)
        assert "```python" in result
        assert "<<<SEARCH" in result
        assert ">>>" in result

    def test_already_fenced_unchanged(self):
        """A block that already has code fences is not double-wrapped."""
        result = _ensure_modify_blocks_fenced(SR_FENCED)
        # Should not contain double-fenced markers
        assert result.count("```python") == 1
        assert result == SR_FENCED

    def test_language_inferred_from_yaml_extension(self):
        """Language is inferred from the file extension (yaml → yaml)."""
        result = _ensure_modify_blocks_fenced(SR_YAML_BARE)
        assert "```yaml" in result

    def test_no_sr_markers_not_touched(self):
        """Blocks without S/R markers (just prose) are left unchanged."""
        result = _ensure_modify_blocks_fenced(SR_NO_MARKERS)
        assert "```" not in result
        assert result == SR_NO_MARKERS

    def test_dunder_escaped_path_handled(self):
        """Escaped dunder paths like \\_\\_ are correctly handled for lang detection."""
        result = _ensure_modify_blocks_fenced(SR_DUNDER_BARE)
        # Should use python for .py files (after stripping escape sequences)
        assert "```python" in result

    def test_multiple_blocks_all_fixed(self):
        """Multiple bare [MODIFY] blocks in the same runbook are all fixed."""
        content = SR_BARE + "\n" + SR_YAML_BARE
        result = _ensure_modify_blocks_fenced(content)
        assert result.count("```python") == 1
        assert result.count("```yaml") == 1

    def test_mixed_fenced_and_bare(self):
        """Only bare blocks are fixed; already-fenced blocks are untouched."""
        content = SR_FENCED + "\n" + SR_BARE.replace("check.py", "other.py")
        result = _ensure_modify_blocks_fenced(content)
        # SR_FENCED contributes 1, SR_BARE for other.py adds 1
        assert result.count("```python") == 2

    def test_new_blocks_not_affected(self):
        """[NEW] blocks are not targeted by this function."""
        content = """#### [NEW] .agent/src/new_file.py
def hello():
    pass
"""
        result = _ensure_modify_blocks_fenced(content)
        # No change — this is a [NEW] block, not [MODIFY]
        assert result == content
