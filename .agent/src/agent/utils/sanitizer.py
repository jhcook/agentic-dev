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
Utility functions for sanitizing text to protect PII and sensitive credentials.
"""

import re
from typing import List, Pattern

# Regular expressions for common sensitive data types
# 1. Emails
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# 2. IPv4 Addresses
IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

# 3. Credit Cards (Generic 13-16 digits)
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

# 4. API Keys and Secrets (heuristic: 16+ chars following a sensitive label)
# Captures group 1 as the secret value to allow targeted masking
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(?:key|secret|token|password|auth|credential|api_key|private_key|bearer)"
    r"[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9\-_.~]{16,})[\"']?"
)

# 5. Authorization Bearer Tokens
BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*")

# 6. PEM Private Keys
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL)

def scrub_text(text: str, mask: str = "[REDACTED]") -> str:
    """
    Remove PII and sensitive credentials from a string.

    Args:
        text: The raw string to sanitize.
        mask: The string to replace sensitive matches with.

    Returns:
        The sanitized string.
    """
    if not text or not isinstance(text, str):
        return text

    sanitized = text
    
    # 1. Scrub Secrets/API Keys - replaces only the value part captured in Group 1
    def _mask_secret(match: re.Match) -> str:
        full_match = match.group(0)
        secret_part = match.group(1)
        return full_match.replace(secret_part, mask)
    
    sanitized = SECRET_VALUE_PATTERN.sub(_mask_secret, sanitized)

    # 2. Scrub other simple patterns
    simple_patterns = [
        EMAIL_PATTERN, 
        IP_PATTERN, 
        CREDIT_CARD_PATTERN, 
        BEARER_PATTERN, 
        PRIVATE_KEY_PATTERN
    ]
    for pattern in simple_patterns:
        sanitized = pattern.sub(mask, sanitized)

    return sanitized

def is_clean(text: str) -> bool:
    """
    Check if the text contains any identifiable PII or secrets.

    Returns:
        True if no sensitive data is detected, False otherwise.
    """
    patterns = [
        EMAIL_PATTERN, 
        IP_PATTERN, 
        CREDIT_CARD_PATTERN, 
        SECRET_VALUE_PATTERN, 
        BEARER_PATTERN, 
        PRIVATE_KEY_PATTERN
    ]
    return all(not p.search(text) for p in patterns)
