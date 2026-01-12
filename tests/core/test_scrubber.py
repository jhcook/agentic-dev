import pytest
from agent.core.utils import scrub_sensitive_data

def test_scrub_sensitive_data_emails():
    # Use real-looking email mixed with text
    input_text = "Please contact admin@corp.com for assistance."
    expected_partial = "Please contact [REDACTED:EMAIL] for assistance."
    
    scrubbed = scrub_sensitive_data(input_text)
    
    # Assert redaction happened
    assert "[REDACTED:EMAIL]" in scrubbed
    # Assert original secret is gone
    assert "admin@corp.com" not in scrubbed
    # Assert structure is preserved
    assert scrubbed == expected_partial

def test_scrub_sensitive_data_ips():
    input_text = "Host: 10.0.0.5 connected."
    scrubbed = scrub_sensitive_data(input_text)
    assert "[REDACTED:IP]" in scrubbed
    assert "10.0.0.5" not in scrubbed

def test_scrub_sensitive_data_api_keys():
    # Real-length dummy keys
    openai_key = "sk-" + "a" * 48
    gh_key = "ghp_" + "b" * 36
    google_key = "AIza" + "c" * 35
    
    input_text = f"Config: {openai_key} / {gh_key} / {google_key}"
    scrubbed = scrub_sensitive_data(input_text)
    
    # Check all types
    assert "[REDACTED:OPENAI_KEY]" in scrubbed
    assert "[REDACTED:GITHUB_KEY]" in scrubbed
    assert "[REDACTED:GOOGLE_KEY]" in scrubbed
    
    # Check total removal
    assert openai_key not in scrubbed
    assert gh_key not in scrubbed
    assert google_key not in scrubbed

def test_scrub_sensitive_data_private_key():
    # Full block to ensure regex handles multiline or header logic if needed (regex currently just header)
    # But let's test specific header matching as implemented
    key_header = "-----BEGIN RSA PRIVATE KEY-----"
    key_body = "MIIEpQIBAAKCAQEA..."
    input_text = f"{key_header}\n{key_body}"
    
    scrubbed = scrub_sensitive_data(input_text)
    
    assert "[REDACTED:PRIVATE_KEY]" in scrubbed
    # Ensure the marker that triggers it is gone/replaced
    assert "-----BEGIN RSA PRIVATE KEY-----" not in scrubbed

def test_scrub_no_secrets():
    text = "Hello world! This is safe code."
    assert scrub_sensitive_data(text) == text

def test_scrub_empty():
    assert scrub_sensitive_data("") == ""
    assert scrub_sensitive_data(None) == ""
