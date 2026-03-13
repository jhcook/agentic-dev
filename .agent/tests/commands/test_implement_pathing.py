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

from unittest.mock import patch

from agent.commands.implement import apply_change_to_file, find_file_in_repo


@patch("agent.core.implement.orchestrator.subprocess.check_output")
def test_find_file_in_repo(mock_subprocess):
    # Mock git output
    mock_subprocess.return_value = b"src/legacy/main.py\nsrc/agent/main.py"
    
    results = find_file_in_repo("main.py")
    assert "src/legacy/main.py" in results
    assert "src/agent/main.py" in results

@patch("agent.commands.implement.typer.confirm")
@patch("agent.core.implement.resolver._find_file_in_repo")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.write_text")
@patch("builtins.open")
def test_apply_auto_correct(mock_open, mock_write, mock_exists, mock_find, mock_confirm):
    """apply_change_to_file succeeds when resolve_path auto-corrects to the unique match."""
    # Root "custom_script.py" does NOT exist ...
    mock_exists.return_value = False
    # ... but git-ls-files finds exactly one real location
    mock_find.return_value = [".agent/src/agent/custom_script.py"]

    success = apply_change_to_file("custom_script.py", "print('hello')", yes=True)

    # The file should have been written successfully
    assert success is True
    # write_text must have been called (file was created in resolved location)
    mock_write.assert_called_once()
