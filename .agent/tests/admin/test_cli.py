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
from agent.commands.admin import ProcessManager
import signal
import sys

@pytest.fixture
def process_manager():
    return ProcessManager()

def test_start_success(process_manager, tmp_path):
    """Test starting backend and frontend successfully."""
    # Create real directory structure for Path.exists() checks
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    (tmp_path / ".agent" / "src" / "web").mkdir(parents=True)
    (tmp_path / ".agent" / "logs").mkdir(parents=True)

    # Patch config paths to use tmp_path
    with patch("subprocess.Popen") as mock_popen, \
         patch("agent.commands.admin.open", new_callable=MagicMock), \
         patch.object(process_manager, "_get_pids", return_value=None), \
         patch.object(process_manager, "_write_pids") as mock_write, \
         patch.object(process_manager, "_is_port_in_use", return_value=False), \
         patch("agent.commands.admin.validate_credentials"), \
         patch("agent.commands.admin.config") as mock_config:
        
        mock_config.repo_root = tmp_path
        mock_config.agent_dir = tmp_path / ".agent"
        mock_config.log_dir = tmp_path / ".agent" / "logs"
        
        mock_backend = MagicMock()
        mock_backend.pid = 123
        mock_frontend = MagicMock()
        mock_frontend.pid = 456
        
        mock_popen.side_effect = [mock_backend, mock_frontend]
        
        process_manager.start(follow=False)
        
        assert mock_popen.call_count == 2
        # Verify backend call
        args_be, kwargs_be = mock_popen.call_args_list[0]
        assert "python" in args_be[0][0]
        assert "uvicorn" in args_be[0]
        
        # Verify frontend call
        args_fe, kwargs_fe = mock_popen.call_args_list[1]
        assert args_fe[0] == ["npm", "run", "dev"]
        
        mock_write.assert_called_with(123, 456)

def test_stop_success(process_manager):
    """Test stopping processes."""
    with patch.object(process_manager, "_get_pids", return_value={"backend_pid": 123, "frontend_pid": 456}), \
         patch("os.kill", side_effect=ProcessLookupError) as mock_kill, \
         patch("os.killpg") as mock_killpg, \
         patch.object(process_manager, "_clean_pid_file") as mock_clean:
         
        process_manager.stop()
        
        if sys.platform != "win32":
            assert mock_killpg.call_count == 2
            mock_killpg.assert_any_call(123, signal.SIGTERM)
            mock_killpg.assert_any_call(456, signal.SIGTERM)
        else:
            assert mock_kill.call_count == 2
            mock_kill.assert_any_call(123, signal.SIGTERM)
            mock_kill.assert_any_call(456, signal.SIGTERM)
        
        mock_clean.assert_called_once()
