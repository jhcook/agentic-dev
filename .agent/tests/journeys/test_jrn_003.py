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

"""AI-generated regression tests for JRN-003."""
import pytest
pytestmark = pytest.mark.skip(reason="AI generated test requires update")
import subprocess

@pytest.mark.journey("JRN-003")
def test_jrn_003_step_1():
    """Developer runs `agent list`
    Assertions: Command exits with status 0, Expected output displayed
    """
    result = subprocess.run(['agent', 'list'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Available agents:" in result.stdout