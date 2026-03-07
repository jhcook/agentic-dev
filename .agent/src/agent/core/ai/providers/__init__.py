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
"""AI provider package — factory and registry for concrete AIProvider backends.

Responsible for mapping provider name strings to concrete AIProvider instances
via a lazy-import factory that avoids circular imports at module load time.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional, Type

from agent.core.ai.protocols import AIProvider

logger = logging.getLogger(__name__)

# Maps provider name -> dotted class path (lazy-imported to prevent circular imports)
_PROVIDER_CLASS_MAP: Dict[str, str] = {
    "openai": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini": "agent.core.ai.providers.vertex.VertexAIProvider",
    "vertex": "agent.core.ai.providers.vertex.VertexAIProvider",
    "anthropic": "agent.core.ai.providers.anthropic.AnthropicProvider",
    "ollama": "agent.core.ai.providers.ollama.OllamaProvider",
    "gh": "agent.core.ai.providers.gh.GHProvider",
    "mock": "agent.core.ai.providers.mock.MockProvider",
}

# Model-prefix fallback for unknown model name strings
_PREFIX_FALLBACKS: Dict[str, str] = {
    "gpt-": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini-": "agent.core.ai.providers.vertex.VertexAIProvider",
}

# Runtime cache: provider name -> resolved class
PROVIDERS: Dict[str, Type] = {}


def _resolve_class(dotted: str) -> Type:
    """Import and return a class from a dotted module path."""
    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_provider(
    name: str,
    client: Optional[Any] = None,
    model_name: Optional[str] = None,
) -> AIProvider:
    """Return a concrete AIProvider instance for *name*.

    Performs lazy class resolution to prevent circular imports.  Falls back to
    prefix matching (``gpt-`` → OpenAI, ``gemini-`` → Vertex) for unknown
    model-name strings, then defaults to OpenAI for fully unknown names.

    Args:
        name: Provider identifier (e.g. ``"openai"``, ``"vertex"``) **or** a
            model name string (e.g. ``"gpt-4o"``).
        client: Optional pre-built SDK client to inject into the provider,
            avoiding re-authentication on every call.
        model_name: Default model identifier for this provider instance.

    Returns:
        A configured ``AIProvider`` instance.
    """
    dotted = _PROVIDER_CLASS_MAP.get(name)

    if not dotted:
        # Try prefix fallback
        for prefix, fallback_dotted in _PREFIX_FALLBACKS.items():
            if name.startswith(prefix):
                dotted = fallback_dotted
                logger.debug(
                    "Provider prefix fallback: %s -> %s", name, fallback_dotted
                )
                break

    if not dotted:
        logger.warning(
            "Unknown provider/model '%s', defaulting to OpenAI", name,
            extra={"provider": name},
        )
        dotted = _PROVIDER_CLASS_MAP["openai"]

    if name not in PROVIDERS:
        PROVIDERS[name] = _resolve_class(dotted)

    cls = PROVIDERS[name]
    effective_model = model_name or (name if name not in _PROVIDER_CLASS_MAP else None)
    return cls(client=client, model_name=effective_model)


__all__ = ["get_provider", "PROVIDERS", "AIProvider"]
