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
from pydantic import BaseModel
from agent.core.adk.tool_security import validate_tool_args, secure_config_injection

class MockSearchSchema(BaseModel):
    query: str
    limit: int = 10

def test_validate_tool_args_success():
    """Verify valid arguments pass schema check."""
    valid_args = {"query": "test execution", "limit": 5}
    assert validate_tool_args("mock_search", valid_args, MockSearchSchema) is True

def test_validate_tool_args_failure():
    """Verify invalid arguments are rejected."""
    # Missing required 'query'
    assert validate_tool_args("mock_search", {"limit": 5}, MockSearchSchema) is False
    # Invalid type for 'limit'
    assert validate_tool_args("mock_search", {"query": "test", "limit": "invalid"}, MockSearchSchema) is False

def test_secure_config_injection_isolation():
    """Verify cross-interface keys are stripped."""
    config = {
        "configurable": {
            "session_id": "voice_123",
            "terminal_size": [80, 24], # Should be removed in voice context
            "admin_esc": True          # Should be removed always
        }
    }
    
    # Test Voice Sanitization
    voice_sanitized = secure_config_injection(config.copy(), "voice")
    assert "session_id" in voice_sanitized["configurable"]
    assert "terminal_size" not in voice_sanitized["configurable"]
    assert "admin_esc" not in voice_sanitized["configurable"]
    
    # Test Console Sanitization
    console_sanitized = secure_config_injection(config.copy(), "console")
    assert "terminal_size" in console_sanitized["configurable"]
    assert "session_id" not in console_sanitized["configurable"]
    assert "admin_esc" not in console_sanitized["configurable"]
