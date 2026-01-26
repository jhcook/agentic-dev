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
from fastapi.testclient import TestClient
from backend.main import app
from pathlib import Path

client = TestClient(app)

CACHE_DIR = Path(".agent/cache")

@pytest.fixture
def mock_story(tmp_path):
    # This assumes the backend uses .agent/cache relative to CWD.
    # In a real test we might want to patch CACHE_DIR in the router.
    # For now, let's just check if it returns 200 OK for list.
    pass

def test_list_artifacts():
    response = client.get("/api/admin/governance/artifacts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_graph():
    response = client.get("/api/admin/governance/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data

def test_markdown_parsing_logic():
    # Unit test for the parser function using a mock
    from backend.routers.governance import parse_markdown_links
    
    content = """
    # My Story [WEB-005]
    
    Links to [ADR-004] and [WEB-004].
    """
    
    links = parse_markdown_links(content)
    assert "WEB-005" in links
    assert "ADR-004" in links
    assert "WEB-004" in links
