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

from typing import Protocol, List, Dict, Any, Optional

class Prompter(Protocol):
    """Protocol for abstracting user interactions away from the CLI framework."""
    
    def echo(self, message: str) -> None:
        """Print a standard message."""
        ...
        
    def secho(self, message: str, color: Optional[str] = None, dim: bool = False, bold: bool = False) -> None:
        """Print a styled message."""
        ...
        
    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for a boolean confirmation."""
        ...
        
    def prompt(self, message: str, default: str = "") -> str:
        """Prompt for text input."""
        ...
        
    def getpass(self, message: str) -> str:
        """Prompt for masked password input."""
        ...
        
    def prompt_password_strength(self) -> str:
        """Specialized prompt for creating a new strong password."""
        ...

    def exit(self, code: int = 1) -> None:
        """Exit the application."""
        ...

    def print_table(self, title: str, columns: List[str], rows: List[List[str]]) -> None:
        """Print a formatted table."""
        ...
