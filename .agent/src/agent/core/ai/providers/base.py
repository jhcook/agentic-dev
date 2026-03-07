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
"""Base provider mixin with shared helpers for all AIProvider backends.

Responsible for providing default implementations of non-core AIProvider methods
so that concrete providers only need to implement ``generate()`` and ``stream()``.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class BaseProvider:
    """Shared base class for all concrete AIProvider implementations.

    Provides default implementations of ``supports_tools()`` and
    ``get_models()``.  Subclasses must implement ``generate()`` and
    ``stream()`` to satisfy the ``AIProvider`` protocol.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """Initialise the provider.

        Args:
            client: Pre-built SDK client instance injected by ``AIService.reload()``.
                May be ``None`` for providers that construct their own client
                lazily (e.g. ``GHProvider``).
            model_name: Default model identifier for this provider instance.
        """
        self.client = client
        self.model_name = model_name or ""

    def supports_tools(self) -> bool:
        """Return whether this provider supports tool/function calling."""
        return False

    def get_models(self) -> List[str]:
        """Return the model identifier(s) supported by this provider instance."""
        return [self.model_name] if self.model_name else []
