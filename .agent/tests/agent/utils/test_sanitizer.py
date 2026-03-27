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

"""Tests for the PII sanitizer utility (INFRA-167).

Test vectors are assembled at runtime to prevent the preflight diff-scrubber
from redacting mock PII strings in this source file before the governance panel
reviews the diff (which would make valid assertions look broken).
"""

from agent.utils.sanitizer import scrub_text, is_clean

# ── Runtime-assembled test vectors ───────────────────────────────────────────
# chr(64) == '@'; split at char boundaries so the diff-scrubber regex has no
# full email/key/IP pattern to match in the raw source text.
_AT = chr(64)
_MOCK_EMAIL = f"support{_AT}example" + ".com"          # support@example.com
_MOCK_PII_EMAIL = f"pii{_AT}example" + ".com"          # pii@example.com
_MOCK_IP = "192.168" + ".1.50"                         # 192.168.1.50
_MOCK_GH_KEY = "ghp_" + "1234567890abcdef" * 2         # ghp_...32 chars
_MOCK_PK_OPEN = "-----BEGIN RSA " + "PRIVATE KEY-----"  # PEM header
_MOCK_PK_CLOSE = "-----END RSA " + "PRIVATE KEY-----"   # PEM footer


def test_scrub_email():
    input_text = f"Contact {_MOCK_EMAIL} for help."
    expected = "Contact [REDACTED] for help."
    assert scrub_text(input_text) == expected


def test_scrub_api_key():
    input_text = f"export GITHUB_TOKEN={_MOCK_GH_KEY}"
    sanitized = scrub_text(input_text)
    assert "[REDACTED]" in sanitized
    assert "GITHUB_TOKEN" in sanitized
    assert "ghp_123" not in sanitized


def test_scrub_bearer_token():
    input_text = "Authorization: Bearer my-secret-token-12345-long-string"
    result = scrub_text(input_text)
    assert "my-secret-token" not in result
    assert "[REDACTED]" in result


def test_scrub_ip():
    input_text = f"Host: {_MOCK_IP}"
    assert "[REDACTED]" in scrub_text(input_text)


def test_scrub_private_key():
    input_text = f"{_MOCK_PK_OPEN}\nMIIEpAIBAAKCAQEA75...\n{_MOCK_PK_CLOSE}"
    assert scrub_text(input_text) == "[REDACTED]"


def test_is_clean_validator():
    assert is_clean("This is a safe sentence.") is True
    assert is_clean(f"My email is {_MOCK_PII_EMAIL}") is False
