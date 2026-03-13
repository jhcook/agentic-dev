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

"""
Tests for RunbookVerifier.
"""

import pytest
from pathlib import Path
from agent.core.implement.verifier import RunbookVerifier

def test_verifier_exact_match(tmp_path):
    """
    Test that an exact match returns success.
    """
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    print('world')")
    
    verifier = RunbookVerifier(tmp_path)
    success, error = verifier.verify_block("test.py", "def hello():")
    
    assert success is True
    assert error is None

def test_verifier_mismatch(tmp_path):
    """
    Test that a hallucinated block returns an error with context.
    """
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    print('world')")
    
    verifier = RunbookVerifier(tmp_path)
    # Search block has incorrect indentation
    success, error = verifier.verify_block("test.py", "def hello():\nprint('world')")
    
    assert success is False
    assert error is not None
    assert "The SEARCH block does not exactly match" in error.error_message
    assert "def hello():" in error.suggested_context

def test_verifier_file_not_found(tmp_path):
    """
    Test that a missing file returns a clear error.
    """
    verifier = RunbookVerifier(tmp_path)
    success, error = verifier.verify_block("missing.py", "some code")
    
    assert success is False
    assert "File not found" in error.error_message


from unittest.mock import MagicMock
from agent.core.implement.verification_orchestrator import VerificationOrchestrator, RunbookStep

def test_orchestrator_success_first_try():
    """
    Test the successful verification path where no retries are needed.
    It verifies that the orchestration completes on the first attempt without rewrite logic running.
    """
    verifier = MagicMock()
    verifier.verify_block.return_value = (True, None)
    
    ai_service = MagicMock()
    
    orchestrator = VerificationOrchestrator(verifier, ai_service, max_retries=3)
    
    steps = [RunbookStep(action="MODIFY", path="test.py", search="foo", replace="bar")]
    success, current_steps = orchestrator.verify_and_correct(steps)
    
    assert success is True
    assert current_steps == steps
    assert ai_service.complete.call_count == 0

def test_orchestrator_retry_loop_success():
    """
    Test the scenario where verification fails once but succeeds after an LLM rewrite cycle.
    It verifies that the LLM is correctly requested, the search blocks updated, and the verifier retried.
    """
    verifier = MagicMock()
    # First call fails, second call succeeds
    verifier.verify_block.side_effect = [
        (False, MagicMock(file_path="test.py", error_message="fail", search_block="foo")),
        (True, None)
    ]
    
    ai_service = MagicMock()
    # Return mock steps on rewrite
    ai_service.complete.return_value = "File: test.py\n<<<SEARCH\nfixed\n===\nbar\n>>>"
    
    orchestrator = VerificationOrchestrator(verifier, ai_service, max_retries=3)
    
    steps = [RunbookStep(action="MODIFY", path="test.py", search="foo", replace="bar")]
    success, current_steps = orchestrator.verify_and_correct(steps)
    
    assert success is True
    assert current_steps[0].search == "fixed"
    assert ai_service.complete.call_count == 1
    assert verifier.verify_block.call_count == 2
    
    # Assert that the steps passed to the verifier on the second call are the corrected ones
    first_call_args = verifier.verify_block.call_args_list[0][0]
    second_call_args = verifier.verify_block.call_args_list[1][0]
    assert first_call_args == ("test.py", "foo")
    assert second_call_args == ("test.py", "fixed")

def test_orchestrator_terminates_after_max_retries():
    """
    Test the negative case where the system correctly terminates after hitting the 
    maximum number of rewrite attempts when the corrections stay invalid.
    """
    verifier = MagicMock()
    # Always fails
    verifier.verify_block.return_value = (False, MagicMock(file_path="test.py", error_message="fail", search_block="foo"))
    
    ai_service = MagicMock()
    ai_service.complete.return_value = "File: test.py\n<<<SEARCH\nfixed\n===\nbar\n>>>"
    
    orchestrator = VerificationOrchestrator(verifier, ai_service, max_retries=3)
    
    steps = [RunbookStep(action="MODIFY", path="test.py", search="foo", replace="bar")]
    success, current_steps = orchestrator.verify_and_correct(steps)
    
    assert success is False
    assert current_steps[0].search == "fixed"
    assert ai_service.complete.call_count == 3
    assert verifier.verify_block.call_count == 4