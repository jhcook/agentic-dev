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

from typing import List

class MissingCredentialsError(Exception):
    """Raised when required credentials are missing from both env vars and secret store."""
    
    def __init__(self, missing_keys: List[str]):
        self.missing_keys = missing_keys
        super().__init__(self._build_message())
        
    def _build_message(self) -> str:
        keys_list = ", ".join(self.missing_keys)
        return (
            f"\n[bold red]❌ Missing Credentials[/bold red]\n"
            f"The following required credentials are not found:\n"
            f"  - {keys_list}\n\n"
            f"[yellow]Resolution:[/yellow]\n"
            f"1. Set them as environment variables (e.g., export {self.missing_keys[0]}=...)\n"
            f"2. OR Add them to the secret store using: [bold]agent onboard[/bold]\n"
        )
