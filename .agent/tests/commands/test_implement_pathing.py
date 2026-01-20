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


@patch("agent.commands.implement.subprocess.check_output")
def test_find_file_in_repo(mock_subprocess):
    # Mock git output
    mock_subprocess.return_value = b"src/legacy/main.py\nsrc/agent/main.py"
    
    results = find_file_in_repo("main.py")
    assert "src/legacy/main.py" in results
    assert "src/agent/main.py" in results

@patch("agent.commands.implement.typer.confirm")
@patch("agent.commands.implement.console")
@patch("agent.commands.implement.find_file_in_repo")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.write_text")
@patch("pathlib.Path.mkdir")
def test_apply_auto_correct(mock_mkdir, mock_write, mock_exists, mock_find, mock_console, mock_confirm):
    # Scenario: AI tries to write to "main.py" (root), but it doesn't exist there.
    # It DOES exist at ".agent/src/agent/main.py"
    
    # 1. Root path does NOT exist
    mock_exists.return_value = False 
    
    # 2. Git search finds exactly one match
    mock_find.return_value = [".agent/src/agent/main.py"]
    
    # 3. Apply changes
    success = apply_change_to_file("main.py", "print('hello')", yes=True)
    
    # Assertions
    assert success is True
    # Verify we wrote to the DEEP path, not the root path
    # args[0] of write_text should be the content. The Path object it's called on matters.
    # We can check if console printed the auto-correct message
    mock_console.print.assert_any_call("[yellow]⚠️  Path Auto-Correct (File Match): 'main.py' -> '.agent/src/agent/main.py'[/yellow]")
