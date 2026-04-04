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
from unittest.mock import MagicMock, patch
from agent.commands.audit import log_sr_malformation_event

@patch("agent.commands.audit.log_governance_event")
def test_log_sr_malformation_event(mock_log):
    """Verify that malformed S/R events are correctly routed to the governance logger."""
    file_path = "backend/voice/tools/git.py"
    reason = "empty search block"
    action = "skipped"
    
    log_sr_malformation_event(file_path, reason, action)
    
    mock_log.assert_called_once()
    args, kwargs = mock_log.call_args
    assert args[0] == "sr_replace_malformed_empty_search"
    assert args[1]["file_path"] == file_path
    assert args[1]["reason"] == reason
    assert args[1]["action"] == action
    assert "timestamp" in args[1]
    assert args[1]["event_code"] == "INFRA-184"
