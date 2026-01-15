import sys
from unittest.mock import patch

from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()

@patch("agent.sync.sync.main")
def test_sync_shim(mock_sync_main):
    # Test that arguments are forwarded correctly
    # We invoke the specific command 'sync' on the main app
    
    result = runner.invoke(app, ["sync", "status", "--verbose"])
    
    assert result.exit_code == 0
    
    # Check that sync.main was called
    mock_sync_main.assert_called_once()
    
    # Verify sys.argv patching
    # Note: sys.argv persists, so this might be flaky if running parallel, 
    # but sequential is fine.
    assert sys.argv[0] == "agent-sync"
    assert "status" in sys.argv
    assert "--verbose" in sys.argv
