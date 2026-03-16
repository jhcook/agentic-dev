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
Formatting utilities for Pydantic validation errors in runbooks.

This module is part of the CLI schema validation gate (INFRA-149). When a
runbook fails Pydantic schema validation, the raw error list is passed to
:func:`format_runbook_errors` which produces human-readable, Rich-compatible
output for immediate display in the terminal.  It handles plain string
errors, Pydantic ``ErrorDict`` structures (with ``loc`` / ``msg`` fields),
and gracefully falls back for unexpected types.
"""

from typing import Any, Dict, List, Union

def format_runbook_errors(errors: List[Union[str, Dict[str, Any]]]) -> str:
    """
    Format a list of validation errors into a human-readable string.

    Handles both raw strings and Pydantic-style error dictionaries.

    Args:
        errors: A list of error messages or Pydantic error dictionaries.

    Returns:
        A formatted markdown string for CLI display.
    """
    if not errors:
        return ""

    lines = ["### SCHEMA VALIDATION FAILED ###"]
    
    for i, err in enumerate(errors, 1):
        if isinstance(err, str):
            lines.append(f"{i}. {err}")
        elif isinstance(err, dict):
            # Handle Pydantic ErrorDict (loc, msg, type)
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Unknown error")
            
            # Identify step index for implementation blocks
            step_marker = ""
            if "steps" in err.get("loc", []):
                for p in err.get("loc", []):
                    if isinstance(p, int):
                        step_marker = f" (Step {p + 1})"
                        break
            
            lines.append(f"{i}. [bold red]{loc}[/bold red]{step_marker}: {msg}")
        else:
            lines.append(f"{i}. {str(err)}")
            
    return "\n".join(lines)