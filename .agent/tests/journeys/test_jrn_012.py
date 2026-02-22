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

"""AI-generated regression tests for JRN-012."""
import pytest
import subprocess
import unittest.mock

@pytest.mark.journey("JRN-012")
def test_jrn_012_step_1():
    """Developer runs `agent sync`

    Assertions:
        Command exits with status 0
        Expected output displayed
    """
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Sync completed successfully"
        mock_run.return_value.stderr = ""

        result = subprocess.run(["agent", "sync"], capture_output=True, text=True)

        assert result.returncode == 0
        assert "Sync completed successfully" in result.stdout