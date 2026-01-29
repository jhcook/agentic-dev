# Patched Content for credentials.py

def validate_credentials():
    # ... existing code ...
    missing_keys = [] # assuming 'missing_keys' is populated with missing credential keys
    if missing_keys:
        provider = 'OpenAI'  # example provider
        logger.warning(f"AUDIT: Missing critical credentials for provider '{provider}'.")
    # ... more code ...

# In a separate UI error handling module (e.g., ui_utils.py)

def handle_cli_error(cli_call_string: str, exception: Exception):
    if isinstance(exception, MissingCredentialsError):
        print(f"ERROR: Missing credentials.  Please check CLI logs for details.")
    else:
        print(f"ERROR: Could not launch command `{cli_call_string}`, check the CLI logs for more information.")
    # Potentially log the full exception for debugging purposes

# Example usage in the UI layer

from ui_utils import handle_cli_error

try:
    cli_call = "agent admin"
    cli_call()
except Exception as e:
    handle_cli_error(cli_call, e)

```

```python
# Patched Content for agent/core/auth/tests/test_validate_credentials.py
import pytest

from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError

def assert_error_message_contains_key_name_but_not_value(error_message: str, key_name: str):
    assert key_name in error_message
    assert "value" not in error_message.lower()


def test_missing_credential_error_message():
    # ... existing test setup ...
    with pytest.raises(MissingCredentialsError) as exc_info:
        validate_credentials()
    error_message = str(exc_info.value)
    assert_error_message_contains_key_name_but_not_value(error_message, "OPENAI_API_KEY")  # Example: Replace with actual key name
    # ... more assertions for other missing keys using the helper function ...
