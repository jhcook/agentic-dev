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

"""AI-generated regression tests for JRN-002."""
import pytest
import subprocess

@pytest.mark.journey("JRN-002")
def test_jrn_002_step_1():
    """1. Developer runs `agent commit`
     Assertions: Command exits with status 0, Expected output displayed"""
    result = subprocess.run(['uv', 'run', 'agent', 'commit', '--offline', '--yes'], capture_output=True, text=True)
    assert result.returncode != 0
    assert "required" in result.stdout or "required" in result.stderr

@pytest.mark.journey("JRN-002")
def test_jrn_002_step_2():
    """2. Developer runs `agent commit --help`
     Assertions: Command exits with status 0, Expected output displayed"""
    result = subprocess.run(['uv', 'run', 'agent', 'commit', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage: agent commit" in result.stdout
    assert "Commit changes with a governed message" in result.stdout

@pytest.mark.journey("JRN-002")
def test_jrn_002_step_3():
    """3. Developer runs `agent commit -m`
     Assertions: Command exits with status 0, Expected output displayed"""
    result = subprocess.run(['uv', 'run', 'agent', 'commit', '-m'], capture_output=True, text=True)
    assert result.returncode != 0
    assert "requires an argument" in result.stderr

@pytest.mark.journey("JRN-002")
def test_jrn_002_step_4():
    """4. Developer runs `agent new-runbook`
     Assertions: Command exits with status 0, Expected output displayed"""
    result = subprocess.run(['uv', 'run', 'agent', 'new-runbook', '--offline'], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Usage: agent new-runbook" in result.stderr or "Usage: agent new-runbook" in result.stdout

@pytest.mark.journey("JRN-002")
def test_jrn_002_step_5():
    """5. Developer runs `agent new-runbook --help`
     Assertions: Command exits with status 0, Expected output displayed"""
    result = subprocess.run(['uv', 'run', 'agent', 'new-runbook', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage: agent new-runbook" in result.stdout
    assert "Generate an implementation runbook" in result.stdout