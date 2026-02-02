import pytest
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture
def mock_artifacts():
    return [
        MagicMock(type="story", status="IN_PROGRESS", id="S-1", dict=lambda: {"id": "S-1", "title": "Story 1", "status": "IN_PROGRESS", "type": "story"}),
        MagicMock(type="story", status="DRAFT", id="S-2", dict=lambda: {"id": "S-2", "title": "Story 2", "status": "DRAFT", "type": "story"}),
        MagicMock(type="adr", status="ACCEPTED", id="ADR-1", dict=lambda: {"id": "ADR-1", "title": "ADR 1", "status": "ACCEPTED", "type": "adr"}),
    ]

@patch("backend.routers.dashboard.scan_artifacts")
def test_get_stories(mock_scan, mock_artifacts):
    mock_scan.return_value = mock_artifacts
    response = client.get("/api/dashboard/stories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "S-2"
    assert data[1]["id"] == "S-1"

@patch("backend.routers.dashboard.scan_artifacts")
def test_get_stats(mock_scan, mock_artifacts):
    mock_scan.return_value = mock_artifacts
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["activeStories"] == 2 # IN_PROGRESS + DRAFT are considered active in my impl?
    # Logic in dashboard.py: active = IN_PROGRESS, REVIEW, DRAFT
    # So 2 stories: IN_PROGRESS + DRAFT = 2. Correct.
    assert data["totalADRs"] == 1
