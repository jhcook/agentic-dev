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

# USE_UNIFIED_REGISTRY flag retired as part of INFRA-183 cutover.
# The unified tool registry is now the mandatory canonical path.
# This function is preserved for API compatibility but always returns True.

def use_unified_registry() -> bool:
    """
    Check if the unified tool registry should be used.

    .. deprecated:: INFRA-183
        The unified registry is now mandatory. This function always returns True.
        The USE_UNIFIED_REGISTRY environment variable is no longer honored.

    Returns:
        bool: Always True.
    """
    return True
