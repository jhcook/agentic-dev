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

"""assembly_engine module."""

# Copyright 2026 Justin Cook

import os
import time
from typing import Dict, Optional

from opentelemetry import trace

from agent.core.implement.chunk_models import RunbookSkeleton
from agent.core.implement.telemetry_helper import log_assembly_audit

_tracer = trace.get_tracer(__name__)


class InvalidTemplateError(Exception):
    """Raised when a skeleton template is malformed or assembly fails."""
    pass

class AssemblyEngine:
    """Engine responsible for reconstructing documents from block maps."""

    def assemble(
        self, 
        skeleton: RunbookSkeleton, 
        injections: Optional[Dict[str, str]] = None
    ) -> str:
        """Reconstruct the document from a RunbookSkeleton.

        Ensures exact preservation of whitespace and styling by concatenating
        blocks in their original order. Supports partial content injection.

        Args:
            skeleton: The parsed RunbookSkeleton containing blocks.
            injections: Optional mapping of block IDs to replacement content.

        Returns:
            The fully assembled document string.

        Raises:
            InvalidTemplateError: If the skeleton has no blocks or duplicate IDs.
        """
        with _tracer.start_as_current_span("assembly_engine.assemble") as span:
            start = time.monotonic()
            span.set_attribute("block_count", len(skeleton.blocks))

            if not skeleton.blocks:
                raise InvalidTemplateError("Cannot assemble an empty skeleton.")

            injections = injections or {}
            seen_ids: set[str] = set()
            parts: list[str] = []

            for block in skeleton.blocks:
                if block.id in seen_ids:
                    raise InvalidTemplateError(f"Duplicate block ID detected: {block.id}")
                seen_ids.add(block.id)

                # Use injected content if ID matches, else original block content
                content = injections.get(block.id, block.content)

                parts.append(block.prefix_whitespace)
                parts.append(content)
                parts.append(block.suffix_whitespace)

            result = "".join(parts)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("duration_ms", duration_ms)
            span.set_attribute("injection_count", len(injections))
            log_assembly_audit(
                user=os.environ.get("USER", "unknown"),
                template_version=skeleton.version,
                block_count=len(skeleton.blocks),
                success=True,
                duration_ms=duration_ms,
            )

            return result

