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
Chat backend integration and selection context management.
"""

# Copyright 2026 Justin Cook

import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from textual.containers import VerticalScroll
from textual.widgets import Static
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data
from agent.core.ai.service import ai_service

logger = get_logger(__name__)

class SelectionLog(VerticalScroll):
    """A replacement for RichLog that holds Static widgets to allow for native text selection."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the selection log with an empty history."""
        super().__init__(*args, **kwargs)
        self._history: List[Dict[str, str]] = []

    def write(self, renderable: Any, scroll_end: bool = False) -> None:
        """Write a new renderable to the selection log, optionally scrolling to the end."""
        widget = Static(renderable)
        widget._search_text = getattr(renderable, "markup", str(renderable))
        self.mount(widget)
        if scroll_end:
            self.scroll_end(animate=False)

    def add_selection(self, text: str, source: str):
        """Add a new selection to the log with scrubbing."""
        scrubbed = scrub_sensitive_data(text)
        self._history.append({"text": scrubbed, "source": source})
        logger.debug(f"Selection added from {source}", extra={"source": source})

    def clear(self) -> None:
        """Clear all contents from the selection log and reset history."""
        self.query("*").remove()
        self._history = []

    def get_context(self) -> str:
        """Formats the collected selections for LLM context."""
        return "\n---\n".join([item["text"] for item in self._history])

async def process_chat_stream(stream: AsyncGenerator[Dict[str, Any], None]) -> AsyncGenerator[str, None]:
    """
    Processes raw chunks from AI providers, handles error chunks,
    and yields clean text for the UI.
    """
    full_response = []
    try:
        async for chunk in stream:
            if "error" in chunk:
                error_msg = chunk["error"]
                logger.error(f"Stream error: {error_msg}", extra={"error": error_msg})
                yield f"\n[Error: {error_msg}]"
                return

            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if content:
                yield content
                full_response.append(content)
    except Exception as e:
        logger.exception("Uncaught exception in chat stream processing")
        yield f"\n[Stream Interrupted: {str(e)}]"

def resolve_provider(provider_name: Optional[str] = None) -> Any:
    """Handoff logic to select the backend provider."""
    target = provider_name or "default"
    logger.info(f"Provider handoff initiated: {target}", extra={"provider": target})
    return ai_service.get_provider(target)