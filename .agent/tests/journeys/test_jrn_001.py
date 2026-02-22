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

"""AI-generated regression tests for JRN-001."""
import pytest
import subprocess
import re


@pytest.mark.journey("JRN-001")
def test_jrn_001_step_1():
    """
    Step 1: Developer runs `agent preflight`
    Assertions: Command exits with status 0, Expected output displayed
    """
    try:
        result = subprocess.run(['uv', 'run', 'agent', 'preflight', '--offline'], capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Expected return code 0, but got {result.returncode}"
        assert re.search(r"Preflight", result.stdout) or "ADR Enforcement" in result.stdout, "Expected output not found"

    except subprocess.CalledProcessError as e:
        pytest.fail(f"Command failed with error: {e.stderr}")
    except FileNotFoundError:
        pytest.fail("`agent` command not found. Ensure it is in your PATH.")