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

"""Provides the Claude AI provider, supporting both direct API and AWS Bedrock
transports, with auto-configuration from ``~/.claude/settings.json``.
"""

import contextlib
import os
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator, Union

import anthropic
from anthropic import Anthropic, AnthropicBedrock

from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.protocols import AIConfigurationError
from agent.core.logger import get_logger

logger = get_logger(__name__)

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

def load_claude_settings() -> Dict[str, Any]:
    """
    Loads configuration from ~/.claude/settings.json.
    
    Returns:
        Dict containing the settings or an empty dict if the file doesn't exist or is invalid.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        logger.debug("claude: no settings file found", extra={"path": str(settings_path)})
        return {}

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.error(
                    "claude: settings file is not a valid JSON object",
                    extra={"path": str(settings_path)},
                )
                return {}
            return data
    except json.JSONDecodeError as e:
        logger.error(
            "claude: failed to parse settings JSON",
            extra={"path": str(settings_path), "error": str(e)},
        )
    except Exception as e:
        logger.error(
            "claude: error reading settings file",
            extra={"error": str(e)},
        )
    
    return {}

def _apply_settings_env(settings: Dict[str, Any]) -> None:
    """
    Injects keys from the settings 'env' block into os.environ if not already present.
    """
    env_block = settings.get("env", {})
    if not isinstance(env_block, dict):
        return

    for key, value in env_block.items():
        if key not in os.environ:
            logger.debug("claude: injecting env var from settings", extra={"key": key})
            os.environ[key] = str(value)

def _run_aws_auth_refresh(settings: Dict[str, Any]) -> None:
    """
    Executes the awsAuthRefresh command to refresh SSO credentials if configured.
    """
    cmd_str = settings.get("awsAuthRefresh")
    if not cmd_str or not isinstance(cmd_str, str):
        return

    try:
        # shlex.split safely handles command strings without requiring shell=True
        cmd = shlex.split(cmd_str)
        logger.info("claude: executing auth refresh command", extra={"command": cmd_str})
        
        result = subprocess.run(
            cmd, 
            check=False, 
            timeout=60, 
            capture_output=True, 
            text=True
        )

        if result.returncode == 0:
            logger.info("claude: auth refresh command completed successfully")
        else:
            logger.warning(
                "claude: auth refresh failed",
                extra={
                    "exit_code": result.returncode,
                    "error": result.stderr.strip(),
                },
            )
    except subprocess.TimeoutExpired:
        logger.warning(
            "claude: auth refresh command timed out",
            extra={"timeout_seconds": 60},
        )
    except FileNotFoundError:
        logger.error(
            "claude: auth refresh command not found",
            extra={"command": cmd_str.split()[0]},
        )
    except Exception as e:
        logger.error(
            "claude: unexpected error during auth refresh",
            extra={"error": str(e)},
        )

class ClaudeProvider(BaseProvider):
    """
    Anthropic Claude provider supporting both direct API and AWS Bedrock transports.
    
    Automatically detects configuration from ~/.claude/settings.json to match
    the user's local Claude Code environment.
    """

    client: Union[Anthropic, AnthropicBedrock]

    def __init__(self, model_id: str, **kwargs: Any) -> None:
        """
        Initializes the provider, loading settings and selecting the appropriate SDK client.
        """
        self.model_id = model_id
        
        # 1. Load local settings
        settings = load_claude_settings()
        
        # 2. Inject environment (explicit env always wins)
        _apply_settings_env(settings)
        
        # 3. Refresh Auth (SSO) before client construction
        _run_aws_auth_refresh(settings)

        # 4. Client Selection Branching
        # Detection logic matches Claude Code behavior
        is_bedrock = os.environ.get("CLAUDE_CODE_USE_BEDROCK") == "1"
        
        if is_bedrock:
            logger.info(
                "claude: building AnthropicBedrock client", 
                extra={"transport": "bedrock", "model": model_id}
            )
            region = os.environ.get("AWS_REGION")
            profile = os.environ.get("AWS_PROFILE")
            
            self.client = AnthropicBedrock(
                aws_region=region,
                aws_profile=profile
            )
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise AIConfigurationError(
                    "Claude provider failed to initialize: ANTHROPIC_API_KEY is not set "
                    "and CLAUDE_CODE_USE_BEDROCK is not enabled in settings."
                )
            
            logger.info(
                "claude: building standard Anthropic client",
                extra={"transport": "direct", "model": model_id}
            )
            self.client = Anthropic(api_key=api_key)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion using the Anthropic Messages API.
        """
        span_ctx = _tracer.start_as_current_span("claude.generate") if _tracer else contextlib.nullcontext()
        with span_ctx as span:
            if span:
                span.set_attribute("model", self.model_id)
            try:
                response = self.client.messages.create(
                    model=self.model_id,
                    max_tokens=kwargs.get("max_tokens", 4096),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", 0.7),
                    system=kwargs.get("system_prompt", anthropic.NOT_GIVEN)
                )
                return response.content[0].text
            except anthropic.APIError as e:
                logger.error(
                    "claude: API error",
                    extra={"error": str(e), "model": self.model_id},
                )
                raise e
            except Exception as e:
                logger.error(
                    "claude: unexpected generation error",
                    extra={"error": str(e), "model": self.model_id},
                )
                raise e

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """
        Streams completion chunks using the Anthropic Messages API.
        """
        span_ctx = _tracer.start_as_current_span("claude.stream") if _tracer else contextlib.nullcontext()
        with span_ctx as span:
            if span:
                span.set_attribute("model", self.model_id)
            try:
                with self.client.messages.stream(
                    model=self.model_id,
                    max_tokens=kwargs.get("max_tokens", 4096),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", 0.7),
                    system=kwargs.get("system_prompt", anthropic.NOT_GIVEN)
                ) as stream_response:
                    for text in stream_response.text_stream:
                        yield text
            except anthropic.APIError as e:
                logger.error(
                    "claude: API error during stream",
                    extra={"error": str(e), "model": self.model_id},
                )
                raise e
            except Exception as e:
                logger.error(
                    "claude: unexpected streaming error",
                    extra={"error": str(e), "model": self.model_id},
                )
                raise e
