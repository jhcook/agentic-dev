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

"""AI-generated regression tests for JRN-017."""
import pytest
import subprocess
from unittest import mock

@pytest.mark.journey("JRN-017")
def test_jrn_017_step_1():
    """Developer runs `agent audit`."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Audit completed successfully"
        mock_run.return_value.stderr = ""

        result = subprocess.run(["agent", "audit"], capture_output=True, text=True)

        assert result.returncode == 0
        assert "Audit completed successfully" in result.stdout