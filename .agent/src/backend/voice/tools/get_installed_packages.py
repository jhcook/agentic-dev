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

from langchain_core.tools import tool
import importlib.metadata

@tool
def get_installed_packages() -> str:
    """Returns a list of installed Python packages and their versions."""
    try:
        dists = importlib.metadata.distributions()
        packages_list = sorted([f"{d.metadata['Name']}=={d.version}" for d in dists])
        return "\n".join(packages_list)
    except Exception as e:
        return f"Error listing packages: {e}"
