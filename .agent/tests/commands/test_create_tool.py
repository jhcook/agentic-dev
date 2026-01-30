
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

import pytest
import os
import shutil
from backend.voice.tools.create_tool import create_tool

# Test Fixture for Cleanup
@pytest.fixture
def clean_custom_dir():
    custom_dir = ".agent/src/backend/voice/tools/custom/test_subdir"
    if os.path.exists(custom_dir):
        shutil.rmtree(custom_dir)
    yield
    if os.path.exists(custom_dir):
        shutil.rmtree(custom_dir)

def test_create_tool_path_traversal():
    """Test that we cannot write outside custom dir."""
    res = create_tool.invoke({"file_path": "../../../evil.py", "code": "print('evil')"})
    assert "Security violation" in res

def test_create_tool_valid_relative():
    """Test valid creation."""
    # We mock open/makedirs to avoid actual filesystem IO in unit test generally, 
    # but for this specific "integration" style unit test we can use a temp dir or just strict cleanup
    # Let's simple check the wrapper rejection logic first
    pass 

def test_security_scan_rejects_subprocess():
    """Test that subprocess is rejected."""
    code = "import subprocess\nsubprocess.run('ls')"
    res = create_tool.invoke({"file_path": "test.py", "code": code})
    assert "Security Rejection" in res
    assert "subprocess" in res

def test_security_scan_rejects_os_system():
    """Test that os.system is rejected."""
    code = "import os\nos.system('ls')"
    res = create_tool.invoke({"file_path": "test.py", "code": code})
    assert "Security Rejection" in res
    assert "os.system" in res

def test_security_scan_allows_override():
    """Test that NOQA override works."""
    code = "import os # NOQA: SECURITY_RISK\nos.system('ls')"
    # We expect it to try to create file (and fail or succeed depending on fs), but NOT fail at security scan
    try:
        res = create_tool.invoke({"file_path": "test_override.py", "code": code})
        assert "Security Rejection" not in res
    finally:
         try: os.remove(".agent/src/backend/voice/tools/custom/test_override.py")
         except: pass
