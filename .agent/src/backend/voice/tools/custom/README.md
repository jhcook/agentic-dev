# Custom Voice Agent Tools

This directory contains tools created dynamically by the voice agent or added by developers.

## How to add tools manually

1. Create a python file here, e.g. `my_tool.py`.
2. Use the `@tool` decorator from `langchain_core.tools`.
3. Ensure the tool has a descriptive docstring.
4. Restart the agent (or rely on hot-reloading if triggered via `create_tool`).

## Security Rules

- **Restricted Modules**: `subprocess`, `os.system`, `exec`, `eval` are blocked by default.
- **Override**: If you MUST use these, add `# NOQA: SECURITY_RISK` to the tool source code.
- **Path**: Tools must reside in this directory or subdirectories.

## Example

```python
from langchain_core.tools import tool

@tool
def check_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"The weather in {city} is sunny."
```
