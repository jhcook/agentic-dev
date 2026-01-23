import pytest
from agent.core.security import SecureManager

@pytest.fixture
def secure_manager():
    return SecureManager()

def test_scrub_email(secure_manager):
    text = "Contact support@example.com for help."
    scrubbed = secure_manager.scrub(text)
    assert "support@example.com" not in scrubbed
    assert "[REDACTED:EMAIL]" in scrubbed

def test_scrub_ip_address(secure_manager):
    text = "Server is running at 192.168.1.1 now."
    scrubbed = secure_manager.scrub(text)
    assert "192.168.1.1" not in scrubbed
    assert "[REDACTED:IP]" in scrubbed

def test_scrub_api_key(secure_manager):
    # Use a realistic length key for regex matching (sk- + 32 chars is common)
    key = "sk-1234567890abcdef1234567890abcdef"
    text = f"Use API key {key} for access."
    scrubbed = secure_manager.scrub(text)
    assert key not in scrubbed
    assert "[REDACTED:OPENAI_KEY]" in scrubbed

def test_scrub_multiple_patterns(secure_manager):
    key = "sk-1234567890abcdef1234567890abcdef"
    text = f"User user@test.com logged in from 10.0.0.1 with key {key}"
    scrubbed = secure_manager.scrub(text)
    assert "user@test.com" not in scrubbed
    assert "10.0.0.1" not in scrubbed
    assert key not in scrubbed
    assert "[REDACTED:EMAIL]" in scrubbed
    assert "[REDACTED:IP]" in scrubbed
    assert "[REDACTED:OPENAI_KEY]" in scrubbed

def test_no_secrets(secure_manager):
    text = "Hello world! This is safe text."
    scrubbed = secure_manager.scrub(text)
    assert scrubbed == text
