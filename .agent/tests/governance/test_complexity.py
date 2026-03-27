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

"""test_complexity module."""

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

import pytest
from agent.core.governance.complexity import get_complexity_report

"""Unit tests for deterministic complexity gates (ADR-012)."""

def test_file_loc_thresholds():
    """Verify file-level LOC warnings trigger at > 500 lines."""
    # 100 lines - PASS
    small_content = "print('pass')\n" * 100
    report = get_complexity_report(small_content)
    assert report.file_verdict == "PASS"
    assert report.total_loc == 100

    # 501 lines - WARN
    large_content = "print('warn')\n" * 501
    report = get_complexity_report(large_content)
    assert report.file_verdict == "WARN"

def test_function_length_warn():
    """Verify function length WARN triggers at 21-50 lines."""
    content = """def sample_func():
    # Line 2
""" + "    print('logic')\n" * 23
    
    report = get_complexity_report(content)
    assert len(report.functions) == 1
    fn = report.functions[0]
    assert fn.name == "sample_func"
    assert fn.verdict == "WARN"
    assert 21 <= fn.length <= 50

def test_function_length_block():
    """Verify function length BLOCK triggers at > 50 lines."""
    content = """async def god_function():
    # Massive logic
""" + "    await asyncio.sleep(0)\n" * 55
    
    report = get_complexity_report(content)
    fn = report.functions[0]
    assert fn.verdict == "BLOCK"
    assert fn.length > 50

def test_syntax_error_graceful_fail():
    """Ensure metrics calculation doesn't crash on unparseable files."""
    bad_content = "def broken_syntax(:"
    report = get_complexity_report(bad_content)
    assert report.file_verdict == "PASS"
    assert len(report.functions) == 0
