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

from agent.core.utils import scrub_sensitive_data

def test_scrub_email():
    text = "Contact user@example.com for support."
    scrubbed = scrub_sensitive_data(text)
    assert "user@example.com" not in scrubbed
    assert "[REDACTED:EMAIL]" in scrubbed

def test_scrub_ip_address():
    text = "Server running on 192.168.1.100."
    scrubbed = scrub_sensitive_data(text)
    assert "192.168.1.100" not in scrubbed
    # IP scrubbing might vary, checking for REDACTED
    assert "[REDACTED:IP]" in scrubbed

def test_scrub_api_key():
    # Example heuristic for API key
    text = "Key: sk-1234567890abcdef1234567890abcdef"
    scrubbed = scrub_sensitive_data(text)
    assert "sk-1234567890abcdef1234567890abcdef" not in scrubbed
    assert "[REDACTED:OPENAI_KEY]" in scrubbed

def test_scrub_no_change_safe_text():
    text = "Hello world. This is safe."
    assert scrub_sensitive_data(text) == text
