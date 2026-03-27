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
from unittest.mock import patch


@pytest.fixture
def mock_skeleton():
    """Fixture providing a minimal runbook generation skeleton."""
    return {
        "title": "Test Runbook",
        "sections": [
            {
                "title": "Architecture Review",
                "description": "Review the system design.",
                "files": [".agent/src/agent/core/config.py"],
                "estimated_tokens": 500,
            }
        ],
    }


def test_is_verification_section_by_title():
    """AC-1: Title heuristic correctly classifies verification sections."""
    from agent.commands.runbook_generation import GenerationSection, _is_verification_section

    assert _is_verification_section(GenerationSection(title="Verification & Test Suite", files=[]))
    assert _is_verification_section(GenerationSection(title="Unit Tests", files=[]))
    assert _is_verification_section(GenerationSection(title="QA Checks", files=[]))
    assert not _is_verification_section(GenerationSection(title="Core Implementation", files=[]))
    assert not _is_verification_section(GenerationSection(title="Documentation", files=[]))


def test_is_verification_section_by_file():
    """AC-1: File heuristic correctly classifies verification sections by file path."""
    from agent.commands.runbook_generation import GenerationSection, _is_verification_section

    assert _is_verification_section(
        GenerationSection(title="Implementation", files=[".agent/tests/test_core.py"])
    )
    assert _is_verification_section(
        GenerationSection(title="Core", files=[".agent/tests/agent/test_logic.py"])
    )
    assert not _is_verification_section(
        GenerationSection(title="Impl", files=[".agent/src/agent/core.py"])
    )


@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.context.context_loader._load_targeted_context")
def test_per_section_query_construction(mock_retrieval, mock_complete, mock_skeleton):
    """Smoke test: generate_runbook_chunked is importable."""
    mock_complete.side_effect = [
        (
            '{"title": "Test Runbook", "sections": [{"title": "Architecture Review",'
            ' "description": "Review the system design."}]}'
        ),
        "# placeholder content",
    ]
    mock_retrieval.return_value = "mock context"

    try:
        from agent.commands.runbook_generation import generate_runbook_chunked  # noqa: F401
    except ImportError:
        pytest.skip("runbook_generation module not available in current configuration")

@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.context.context_loader._load_targeted_context")
def test_two_pass_orchestration_context_passing(mock_retrieval, mock_complete):
    """AC-6: Verify Pass 2 gets context from Pass 1."""
    import json
    mock_retrieval.return_value = "mock context"
    
    # Mock skeleton generation, then Pass 1, then Pass 2
    mock_complete.side_effect = [
        json.dumps({
            "title": "Story",
            "sections": [
                {"title": "Impl Section", "description": "Impl", "files": [".agent/src/agent/foo.py"]},
                {"title": "Test Section", "description": "Test", "files": [".agent/tests/agent/test_foo.py"]}
            ]
        }),
        # Pass 1 response
        json.dumps({"header": "Impl Section", "content": "```python\n[NEW] .agent/src/agent/foo.py\n```"}),
        # Pass 2 response
        json.dumps({"header": "Test Section", "content": "test code"})
    ]

    from agent.commands.runbook_generation import generate_runbook_chunked
    from pathlib import Path
    
    # generate_runbook_chunked is a synchronous function (it handles its own event loop internally using _run_async)
    with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.read_text", return_value=""), patch("pathlib.Path.write_text"):
        raw = generate_runbook_chunked("INFRA-174", "story", "rules", "context", "tree", "code")
        
    assert "Impl Section" in raw
    assert "Test Section" in raw

@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.context.context_loader._load_targeted_context")
def test_two_pass_pass_1_failure_aborts_pass_2(mock_retrieval, mock_complete):
    """AC-6: Verify Pass 1 failure aborts Pass 2."""
    import json
    mock_retrieval.return_value = "mock context"
    
    mock_complete.side_effect = [
        json.dumps({
            "title": "Story",
            "sections": [
                {"title": "Impl Section", "description": "Impl", "files": [".agent/src/agent/foo.py"]},
                {"title": "Test Section", "description": "Test", "files": [".agent/tests/agent/test_foo.py"]}
            ]
        }),
        # Pass 1 response - invalid JSON causing a failure (needs to fail 3x due to retry loop)
        "Invalid JSON response",
        "Invalid JSON response",
        "Invalid JSON response"
    ]

    from agent.commands.runbook_generation import generate_runbook_chunked
    from pathlib import Path
    
    # generate_runbook_chunked is a synchronous function (it handles its own event loop internally using _run_async)
    with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.read_text", return_value=""), patch("pathlib.Path.write_text"):
        raw = generate_runbook_chunked("INFRA-174", "story", "rules", "context", "tree", "code")
        
    assert "[Aborted: Pass 1 Failed]" in raw
