# Copyright 2026 Justin Cook
"""Unit tests for the TUI prompts module."""

import pytest
from agent.tui.prompts import _build_clinical_prompt, build_chat_history
from agent.tui.session import Message

def test_build_clinical_prompt():
    """Verify fallback system prompt includes necessary contexts."""
    prompt = _build_clinical_prompt("test-agent", "/test/path", "# License")
    assert "test-agent" in prompt
    assert "/test/path" in prompt
    assert "# License" in prompt

def test_build_chat_history():
    """Verify history construction formats correctly."""
    msgs = [
        Message(role="user", content="Hi"),
        Message(role="assistant", content="Hello")
    ]
    history = build_chat_history(msgs, "What next?")
    assert "User: Hi" in history
    assert "Assistant: Hello" in history
    assert "User: What next?" in history
