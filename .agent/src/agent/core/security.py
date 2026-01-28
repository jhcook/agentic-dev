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
Security utilities for the Agent CLI.
Handles PII and secret scrubbing.
"""
import re

def scrub_sensitive_data(text: str) -> str:
    """
    Scrub potentially sensitive data (emails, API keys) from text.
    """
    if not text:
        return text

    # Email addresses
    text = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", 
        "[REDACTED_EMAIL]", 
        text
    )

    # Generic API Keys (high entropy alphanumeric strings, e.g., sk-..., gcp-...)
    # Matches strings that start with standard prefixes or look like high entropy hashes
    patterns = [
        r"(sk-[a-zA-Z0-9]{20,})",  # OpenAI style
        r"(AIza[0-9A-Za-z-_]{35})", # Google API Key
        r"(ghp_[a-zA-Z0-9]{36})",   # GitHub Personal Access Token
        r"(glpat-[a-zA-Z0-9\-]{20})", # GitLab
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, "[REDACTED_SECRET]", text)

    return text
