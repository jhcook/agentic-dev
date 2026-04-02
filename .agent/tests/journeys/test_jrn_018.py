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

"""AI-generated regression tests for JRN-018."""
import pytest
import subprocess
import shutil

@pytest.mark.journey("JRN-018")
def test_jrn_018_step_1():
    """Developer runs `agent config`."""
    if not shutil.which("agent"):
        pytest.skip("`agent` not in PATH — run via `uv run agent`")
    result = subprocess.run(["agent", "config"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "Usage:" in result.stderr or "Usage:" in result.stdout

@pytest.mark.journey("JRN-018")
def test_jrn_018_step_2():
    """Developer runs `agent config --help`."""
    if not shutil.which("agent"):
        pytest.skip("`agent` not in PATH — run via `uv run agent`")
    result = subprocess.run(["agent", "config", "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--help" in result.stdout

@pytest.mark.journey("JRN-018")
def test_jrn_018_step_3():
    """Developer runs `agent config list`."""
    if not shutil.which("agent"):
        pytest.skip("`agent` not in PATH — run via `uv run agent`")
    result = subprocess.run(["agent", "config", "list"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "No configuration file found" in result.stdout or "No configuration file found" in result.stderr or "agent.yaml" in result.stdout or "router.yaml" in result.stdout

@pytest.mark.journey("JRN-018")
def test_jrn_018_step_4():
    """Developer runs `agent preflight`."""
    if not shutil.which("agent"):
        pytest.skip("`agent` not in PATH — run via `uv run agent`")
    result = subprocess.run(["agent", "preflight", "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Usage:" in result.stdout