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
# distributed under the License is distributed on an "AS IS" BASIS, Dress
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logging utilities for structured events."""

from typing import Any, Dict
from agent.core.logger import get_logger

logger = get_logger(__name__)

def log_section_context_loaded(section_title: str, chunk_count: int, latency_ms: float):
    """Log a structured event when a section's context is successfully retrieved.

    Args:
        section_title: The title of the runbook section.
        chunk_count: Number of relevant code chunks retrieved from Chroma.
        latency_ms: Time taken for the vector query in milliseconds.
    """
    logger.info(
        "section_context_loaded",
        extra={
            "section_title": section_title,
            "chunk_count": chunk_count,
            "query_latency_ms": round(latency_ms, 2),
        },
    )