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

"""feature_flags module."""

import os

def use_unified_registry() -> bool:
    """
    Check if the unified tool registry should be used.

    This function reads the USE_UNIFIED_REGISTRY environment variable.
    It defaults to True, enabling the unified registry pattern introduced in INFRA-145.
    Setting this to 'false' allows the system to fall back to legacy direct tool instantiation.

    Returns:
        bool: True if the unified registry is enabled, False otherwise.
    """
    return os.getenv("USE_UNIFIED_REGISTRY", "true").lower() == "true"
