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
from backend.voice.tools.create_tool import create_tool
from backend.voice.tools.read_tool_source import read_tool_source
from backend.voice.tools.security import scan_file_for_secrets
from backend.voice.tools.get_installed_packages import get_installed_packages

@pytest.fixture
def cleanup_custom_tools():
    # Build absolute path matching what create_tool uses
    import backend.voice.tools.create_tool as ct_module
    custom_dir = os.path.join(os.path.dirname(os.path.abspath(ct_module.__file__)), "custom")
    test_file = os.path.join(custom_dir, "integration_test_tool.py")
    dirty_file = os.path.join(custom_dir, "dirty.py")
    
    # Pre-clean
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(dirty_file):
        os.remove(dirty_file)
        
    yield
    
    # Post-clean
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(dirty_file):
        os.remove(dirty_file)

def test_full_tool_lifecycle(cleanup_custom_tools):
    import os # Force import to avoid weird scope issues
    """
    Integration test:
    1. Create a tool securely
    2. Read it back (verifying silent tags)
    3. Scan it for secrets
    4. Verify it's in the registry (logic check)
    """
    
    filename = "integration_test_tool.py"
    # Build absolute path matching what create_tool uses internally
    import backend.voice.tools.create_tool as ct_module
    custom_dir = os.path.join(os.path.dirname(os.path.abspath(ct_module.__file__)), "custom")
    os.makedirs(custom_dir, exist_ok=True)
    
    abs_path = os.path.join(custom_dir, filename)
    code = """
from langchain_core.tools import tool

@tool
def my_integration_test_tool() -> str:
    \"\"\"Returns success.\"\"\"
    return "SUCCESS"
"""
    
    # 1. Create
    print(f"Creating tool at {abs_path}")
    res = create_tool.invoke({"file_path": filename, "code": code})
    print(f"Creation Result: {res}")
    assert "Success" in res
    assert os.path.exists(abs_path)
    
    # 2. Read Source (Check Silent Tags)
    source = read_tool_source.invoke({"file_path": abs_path})
    assert "<silent>" in source
    assert "</silent>" in source
    assert "SYSTEM INSTRUCTION" in source
    
    # 3. Security Scan (Clean)
    scan_res = scan_file_for_secrets.invoke({"file_path": abs_path})
    assert "No obvious secrets found" in scan_res
    
    # 4. Security Scan (Dirty)
    dirty_path = os.path.join(custom_dir, "dirty.py")
    with open(dirty_path, "w") as f:
        f.write("api_key = 'sk-12345678901234567890'")
        f.write("\nemail = 'test@example.com'")
        
    scan_res_dirty = scan_file_for_secrets.invoke({"file_path": dirty_path})
    assert "Potential API Key found" in scan_res_dirty
    assert "Potential Email found" in scan_res_dirty

def test_package_listing():
    """Verify package listing works."""
    res = get_installed_packages.invoke({})
    assert len(res) > 0
    assert "==" in res
