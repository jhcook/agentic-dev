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

"""Orchestration of multi-layered scrubbing for AI prompt safety."""

import logging
from agent.core.security import scrub_sensitive_data
from agent.core.governance.security import sanitize_tree_output

logger = logging.getLogger(__name__)

def prepare_safe_prompt_context(raw_context: str, is_tree: bool = False) -> str:
    """Apply scrubbing and blocklist filtering to prompt context.

    Args:
        raw_context: The raw data (diff, story, or tree) to be sanitized.
        is_tree: Whether the context is a file tree structure.

    Returns:
        A safe version of the string for AI submission.
    """
    if not raw_context:
        return ""

    safe_text = raw_context

    # 1. Apply Path-based Filtering if it's a file tree
    if is_tree:
        safe_text = sanitize_tree_output(safe_text)

    # 2. Apply Deterministic Regex Scrubbing (PII, API Keys, Credentials)
    try:
        safe_text = scrub_sensitive_data(safe_text)
    except Exception as e:
        logger.error("Scrubbing failed: %s", e)
        # If scrubbing fails, return a high-safety placeholder to prevent leak
        return "[ERROR: CONTENT SUPPRESSED FOR SECURITY]"

    return safe_text