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

"""tool_security module."""

from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from agent.core.logger import get_logger

logger = get_logger(__name__)

def validate_tool_args(tool_name: str, args: Dict[str, Any], schema: Any) -> bool:
    """Strictly validate tool arguments against the provided schema.

    Args:
        tool_name: The name of the tool being called.
        args: The arguments passed to the tool.
        schema: The pydantic model or schema object for validation.

    Returns:
        bool: True if valid, False otherwise.
    """
    if not schema:
        logger.warning(f"No schema found for tool {tool_name}. Blocking execution for safety.")
        return False
    try:
        # Ensure we are using the pydantic model to validate the raw dict
        if hasattr(schema, 'model_validate'):
            schema.model_validate(args)
        elif hasattr(schema, 'parse_obj'):
            schema.parse_obj(args)
        else:
            schema(**args)
        return True
    except (ValidationError, TypeError, ValueError) as e:
        logger.error(f"Schema validation failed for tool {tool_name}: {e}")
        return False

def secure_config_injection(config: Dict[str, Any], interface_type: str) -> Dict[str, Any]:
    """Sanitize RunnableConfig based on interface type to prevent privilege escalation.

    Args:
        config: The RunnableConfig dictionary to sanitize.
        interface_type: The type of interface ('voice' or 'console').

    Returns:
        Dict[str, Any]: The sanitized configuration dictionary.
    """
    # Whitelist of allowed configurable keys per interface
    # This prevents cross-interface spoofing or unauthorized param injection
    SAFE_KEYS = {
        "voice": ["session_id", "voice_settings", "stream_id", "is_streaming", "language"],
        "console": ["terminal_size", "theme", "history_limit", "user_env", "interactive"]
    }
    
    if "configurable" not in config:
        return config
            
    allowed = SAFE_KEYS.get(interface_type, [])
    original_configurable = config.get("configurable", {})
    
    sanitized_configurable = {
        k: v for k, v in original_configurable.items() 
        if k in allowed
    }
    
    # Security logging for stripped keys
    removed_keys = set(original_configurable.keys()) - set(sanitized_configurable.keys())
    if removed_keys:
        logger.warning(f"Stripped unauthorized configurable keys from {interface_type} context: {removed_keys}")

    config["configurable"] = sanitized_configurable
    return config
