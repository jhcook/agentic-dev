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

"""AI-generated regression tests for JRN-005."""
import pytest
pytestmark = pytest.mark.skip(reason="AI generated test requires update")
import subprocess

@pytest.mark.journey("JRN-005")
def test_jrn_005_step_1():
    """Developer runs `agent lint`
    Assertions: Command exits with status 0, Expected output displayed
    """
    expected_output = "No issues found."
    result = subprocess.run(['agent', 'lint'], capture_output=True, text=True)

    assert result.returncode == 0
    assert expected_output in result.stdout

@pytest.mark.journey("JRN-005")
def test_jrn_005_step_2():
    """Developer runs `agent lint --all`
    Assertions: Command exits with status 0, Expected output displayed
    """
    expected_output = "No issues found."
    result = subprocess.run(['agent', 'lint', '--all'], capture_output=True, text=True)

    assert result.returncode == 0
    assert expected_output in result.stdout