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

import json
import pytest
from unittest.mock import patch, MagicMock
from agent.core.governance.audit_handler import record_audit_event, AuditContext

@patch("agent.core.governance.audit_handler._logger")
def test_record_audit_event_serialization(mock_logger):
    """Verify that audit events are correctly formatted as JSON with required fields."""
    domain = "deps"
    action = "add_dependency"
    metadata = {"package": "requests", "version": "2.31.0"}
    
    record_audit_event(domain, action, metadata, status="success")
    
    mock_logger.info.assert_called_once()
    log_msg = mock_logger.info.call_args[0][0]
    assert log_msg.startswith("AUDIT_RECORD:")
    
    # Validate JSON integrity
    json_data = json.loads(log_msg.split(":", 1)[1])
    assert json_data["domain"] == domain
    assert json_data["action"] == action
    assert json_data["status"] == "success"
    assert json_data["metadata"] == metadata
    assert "timestamp" in json_data

@patch("agent.core.governance.audit_handler._logger")
def test_audit_context_success_path(mock_logger):
    """Verify that AuditContext records duration and success on clean exit."""
    with AuditContext("web", "fetch_url", {"url": "https://example.com"}):
        pass
        
    log_msg = mock_logger.info.call_args[0][0]
    json_data = json.loads(log_msg.split(":", 1)[1])
    assert json_data["status"] == "success"
    assert "duration_ms" in json_data["metadata"]
    assert json_data["metadata"]["url"] == "https://example.com"

@patch("agent.core.governance.audit_handler._logger")
def test_audit_context_failure_path(mock_logger):
    """Verify that AuditContext captures exception details on failure."""
    try:
        with AuditContext("context", "rollback", {"checkpoint": "chk_001"}):
            raise ValueError("No checkpoint found")
    except ValueError:
        pass
        
    log_msg = mock_logger.info.call_args[0][0]
    json_data = json.loads(log_msg.split(":", 1)[1])
    assert json_data["status"] == "failure"
    assert json_data["metadata"]["error_type"] == "ValueError"
    assert "No checkpoint found" in json_data["metadata"]["error_message"]
