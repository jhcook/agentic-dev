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

"""AI-generated regression tests for JRN-014."""
import pytest
pytestmark = pytest.mark.skip(reason="AI generated test requires update")
import subprocess

@pytest.mark.journey("JRN-014")
def test_jrn_014_step_1():
    """Developer runs `agent onboard`."""
    try:
        result = subprocess.run(["agent", "onboard"], capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Command failed with error: {result.stderr}"
        assert "Choose between MCP and `gh` CLI" in result.stdout or "Onboarding complete!" in result.stdout, "Expected output not found"
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Command 'agent onboard' failed with error: {e.stderr}")

@pytest.mark.journey("JRN-014")
def test_jrn_014_step_2():
    """Developer runs `agent onboard --help`."""
    try:
        result = subprocess.run(["agent", "onboard", "--help"], capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Command failed with error: {result.stderr}"
        assert "usage: agent onboard" in result.stdout, "Help output not found"
        assert "Interactive onboarding wizard" in result.stdout, "Help output not found"
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Command 'agent onboard --help' failed with error: {e.stderr}")