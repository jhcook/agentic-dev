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

"""
Unit tests for the Git tool module using mock environments.
"""

import json
from pathlib import Path
from unittest.mock import patch
from agent.tools.git import blame, file_history

def test_blame_parsing() -> None:
    """
    Verifies that git blame output is correctly parsed into a structured list.
    """
    # Short format output simulation: <hash> <line>) <content>
    mock_output = """^e123456 1) # License Header
f67890ab 2) def main():
00000000 3)     pass"""
    
    with patch("agent.tools.git._run_git") as mock_git:
        mock_git.return_value = mock_output
        res = blame("main.py", Path("/"))
        
        data = json.loads(res)
        assert len(data) == 3
        assert data[0]["commit"] == "^e123456"
        assert data[0]["line"] == 1
        assert data[0]["content"] == "# License Header"
        assert data[1]["commit"] == "f67890ab"

def test_file_history_parsing() -> None:
    """
    Verifies that git log output is correctly parsed into commit summaries.
    """
    # format: hash|author|date|subject
    mock_output = """hash_one|Justin Cook|2026-01-01|Initial commit
hash_two|Agent|2026-01-02|Updated tools"""

    with patch("agent.tools.git._run_git") as mock_git:
        mock_git.return_value = mock_output
        res = file_history("search.py", Path("/"))
        
        history = json.loads(res)
        assert len(history) == 2
        assert history[0]["author"] == "Justin Cook"
        assert history[0]["summary"] == "Initial commit"
        assert history[1]["commit"] == "hash_two"
        assert history[1]["date"] == "2026-01-02"
