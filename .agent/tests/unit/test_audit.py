
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from agent.core.governance import (
    is_governed,
    find_stagnant_files,
    find_orphaned_artifacts,
    run_audit,
    AuditResult,
    check_license_headers
)

@pytest.fixture
def mock_repo(tmp_path):
    """Create a temporary repo structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo

def test_is_governed_with_header(mock_repo):
    p = mock_repo / "story_file.py"
    p.write_text("# STORY-123: Implemented feature\nprint('hello')")
    governed, msg = is_governed(p)
    assert governed is True
    assert "STORY-123" in msg

def test_is_governed_without_header(mock_repo):
    p = mock_repo / "random.py"
    p.write_text("print('hello')")
    governed, msg = is_governed(p)
    assert governed is False

def test_is_governed_custom_regex(mock_repo):
    p = mock_repo / "custom.py"
    p.write_text("# CUSTOM-123")
    governed, msg = is_governed(p, traceability_regexes=[r"CUSTOM-\d+"])
    assert governed is True

@patch("subprocess.run")
def test_find_stagnant_files(mock_run, mock_repo):
    # Mock git log output
    # file1.py: 2020-01-01 (Old)
    # file2.py: 2025-01-01 (New - assuming current date is 2025/2026)
    
    mock_run.return_value = Mock(stdout="2020-01-01T00:00:00+00:00\nfile1.py\n2026-01-01T00:00:00+00:00\nfile2.py")
    
    # Create the files
    (mock_repo / "file1.py").touch()
    (mock_repo / "file2.py").touch()
    
    # Run with 6 months threshold
    # Since mocked date for file1 is 2020, it should be stagnant
    files = find_stagnant_files(mock_repo, months=6)
    
    # We expect file1.py to be returned if it's not governed
    # By default it's not governed (empty file)
    assert len(files) == 1
    assert files[0]["path"] == "file1.py"

def test_find_orphaned_artifacts(mock_repo):
    cache = mock_repo / ".agent/cache"
    (cache / "stories").mkdir(parents=True)
    
    # Create an old OPEN story
    old_story = cache / "stories/STORY-OLD.json"
    old_story.write_text('{"state": "OPEN", "last_activity": "2020-01-01T00:00:00+00:00"}')
    
    # Create a new OPEN story
    new_story = cache / "stories/STORY-NEW.json"
    new_story.write_text(f'{{"state": "OPEN", "last_activity": "{datetime.now(timezone.utc).isoformat()}"}}')
    
    # Create a CLOSED old story
    closed_story = cache / "stories/STORY-CLOSED.json"
    closed_story.write_text('{"state": "CLOSED", "last_activity": "2020-01-01T00:00:00+00:00"}')
    
    artifacts = find_orphaned_artifacts(cache, days=30)
    
    assert len(artifacts) == 1
    assert artifacts[0]["path"] == "stories/STORY-OLD.json"

@patch("agent.core.governance.find_stagnant_files")
@patch("agent.core.governance.find_orphaned_artifacts")
def test_run_audit_integration(mock_orphaned, mock_stagnant, mock_repo):
    mock_stagnant.return_value = []
    mock_orphaned.return_value = []
    
    # Create some files
    (mock_repo / "governed.py").write_text("# STORY-1")
    (mock_repo / "ungoverned.py").write_text("print('hi')")
    
    result = run_audit(mock_repo)
    
    # 2 files total, 1 governed => 50%
    assert result.traceability_score == 50.0
    assert "ungoverned.py" in result.ungoverned_files

def test_check_license_headers(mock_repo):
    result = AuditResult(0, [], [], [], [])
    
    # File with Apache license
    f1 = mock_repo / "licensed.py"
    f1.write_text("# Licensed under the Apache License, Version 2.0")
    
    # File without
    f2 = mock_repo / "unlicensed.py"
    f2.write_text("print('oops')")
    
    check_license_headers(mock_repo, [f1, f2], [], result)
    
    # Should have error for f2
    assert len(result.errors) == 1
    assert "Missing license headers" in result.errors[0]
