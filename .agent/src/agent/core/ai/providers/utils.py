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

import re
from typing import Optional

def scrub_pii(text: str) -> str:
    """
    Scrubs personally identifiable information (PII) from the given text.
    Replaces emails and potential API keys with redacted placeholders.
    """
    if not text:
        return text
    # Basic email removal
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]", text)
    # Very basic API key removal heuristic (e.g. looks like a key of 32+ chars)
    text = re.sub(r"(?i)(api[_-]?key[\s:=]+)([a-zA-Z0-9]{32,})", r"\1[REDACTED_API_KEY]", text)
    return text

def format_provider_error(error_msg: str, provider_name: str) -> str:
    """
    Format error consistent across providers.
    """
    return f"[{provider_name}] {error_msg}"
