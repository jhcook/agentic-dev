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

from agent.core.security import scrub_sensitive_data

def test_scrub_email():
    text = "Contact support@example.com for help."
    scrubbed = scrub_sensitive_data(text)
    assert "support@example.com" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed

def test_scrub_generic_api_key():
    # Use a realistic length key for regex matching (sk- + chars)
    key = "sk-1234567890abcdef1234567890abcdef"
    text = f"Use API key {key} for access."
    scrubbed = scrub_sensitive_data(text)
    assert key not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed

def test_scrub_multiple_patterns():
    key = "sk-1234567890abcdef1234567890abcdef"
    text = f"User user@test.com logged in with key {key}"
    scrubbed = scrub_sensitive_data(text)
    assert "user@test.com" not in scrubbed
    assert key not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed

def test_no_secrets():
    text = "Hello world! This is safe text."
    scrubbed = scrub_sensitive_data(text)
    assert scrubbed == text
