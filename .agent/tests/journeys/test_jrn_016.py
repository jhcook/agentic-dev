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

"""AI-generated regression tests for JRN-016."""
import pytest
pytestmark = pytest.mark.skip(reason="AI generated test requires update")
import subprocess

@pytest.mark.journey("JRN-016")
def test_jrn_016_step_1():
    """Developer runs `agent query` and checks for successful exit and expected output."""
    try:
        result = subprocess.run(['agent', 'query'], capture_output=True, text=True, check=True)
        assert result.returncode == 0
        assert "Ask AI about the codebase" in result.stdout
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Command failed with error: {e.stderr}")
    except FileNotFoundError:
        pytest.fail("agent command not found. Ensure it's in your PATH.")