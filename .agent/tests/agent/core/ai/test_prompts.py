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
from agent.core.ai.prompts import generate_block_prompt

def test_generate_block_prompt_injects_prior_changes():
    """Validate that prior_changes context is correctly injected into the prompt (AC-4)."""
    section_title = "Test Section"
    section_desc = "Verify the API"
    skeleton_json = "{}"
    story_content = "INFRA-174"
    context_summary = "Existing codebase summary"
    
    prior_changes = {
        ".agent/src/agent/logic.py": "[NEW] created function calculate_sum(a, b)"
    }
    
    prompt = generate_block_prompt(
        section_title=section_title,
        section_desc=section_desc,
        skeleton_json=skeleton_json,
        story_content=story_content,
        context_summary=context_summary,
        prior_changes=prior_changes
    )
    
    assert "FORBIDDEN FILES" in prompt
    assert ".agent/src/agent/logic.py" in prompt
    assert "calculate_sum" in prompt

def test_generate_block_prompt_injects_existing_files():
    """Validate that existing_files block is present to prevent [NEW] on existing files."""
    existing_files = [".agent/src/agent/main.py"]

    prompt = generate_block_prompt(
        "Title", "Desc", "{}", "Story", "Context",
        existing_files=existing_files,
    )

    assert "EXISTING FILES ON DISK" in prompt
    assert ".agent/src/agent/main.py" in prompt
    assert "MUST use [MODIFY], NOT [NEW]" in prompt


def test_generate_block_prompt_accepts_implementation_context():
    """Validate AC-4: implementation_context param is accepted without error."""
    impl_ctx = "def hello():\n    return 'world'"

    prompt = generate_block_prompt(
        section_title="Verification & Test Suite",
        section_desc="Write tests for hello()",
        skeleton_json="{}",
        story_content="INFRA-174",
        context_summary="Existing codebase",
        implementation_context=impl_ctx,
    )

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert impl_ctx in prompt
    assert "IMPLEMENTATION CONTEXT" in prompt


def test_generate_block_prompt_no_context_by_default():
    """Verify implementation_context defaults to None without breaking existing callers."""
    prompt = generate_block_prompt(
        section_title="Architecture Review",
        section_desc="Review design",
        skeleton_json="{}",
        story_content="INFRA-174",
        context_summary="Context",
    )

    assert isinstance(prompt, str)
    assert "Implementation Specialist" in prompt
