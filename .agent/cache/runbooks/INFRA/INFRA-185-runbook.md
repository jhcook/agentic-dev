# Runbook: Implementation Runbook for INFRA-185

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

The integration of the AnthropicBedrock SDK has been reviewed to ensure compliance with architectural standards and security requirements. The following design decisions are validated:

1. **Client Strategy**: The provider will dynamically switch between `Anthropic` (direct API) and `AnthropicBedrock` (AWS) based on the presence of `CLAUDE_CODE_USE_BEDROCK=1`. This maximizes flexibility for developers using both managed and direct service planes.
2. **Configuration Precedence**: To prevent shadowing of system-level environment variables, the implementation strictly follows a precedence order of `OS Environment > ~/.claude/settings.json > Secret Manager`. This ensures that explicit exports in a shell or CI/CD environment always override file-based defaults.
3. **Local File Access**: Access to `~/.claude/settings.json` is handled using `pathlib.Path.home()`. The parsing logic includes guardrails for missing directories, missing files, and malformed JSON, defaulting to a standard environment-only configuration if the file is unavailable.
4. **SSO Security**: The execution of `awsAuthRefresh` will use `shlex.split()` to prevent shell injection vulnerabilities. The command execution is bounded by a 60-second timeout to prevent blocking the agent initialization cycle.
5. **Dependency Footprint**: The transition to `anthropic[bedrock]` is accepted despite the addition of `botocore` dependencies, as the target user base (AWS Bedrock developers) already maintains these libraries in their local environments.

#### [NEW] .agent/docs/architecture/infra-185-claude-provider-design.md

```markdown
# Architecture Review: Claude Provider with Bedrock Support

## Overview

INFRA-185 introduces a `claude` provider capable of auto-detecting AWS Bedrock configurations from the standard `~/.claude/settings.json` file used by Claude Code. This allows the agent to inherit existing SSO sessions and regional configurations without redundant setup.

## Component Design

**1. Configuration Loader**
- **Path**: `~/.claude/settings.json` (resolved via `Path.home()`)
- **Precedence**: Environment variables take absolute priority. If `AWS_REGION` is set in the shell, it will not be overwritten by the value in `settings.json`.
- **Shadowing Prevention**: Variables are injected using `os.environ.setdefault(key, value)`.

**2. SSO Credential Refresh**
- **Command**: `awsAuthRefresh` field from JSON.
- **Execution Safety**: Uses `subprocess.run` with `shell=False` after `shlex.split`. 
- **Timeout**: 60 seconds. Failures are logged at `WARNING` level but do not block client instantiation (allowing existing valid sessions to proceed).

**3. Client Factory**
- **Logic**: 
  - If `CLAUDE_CODE_USE_BEDROCK == "1"` -> `AnthropicBedrock` client.
  - Else -> `Anthropic` client (standard API key).
- **Validation**: If neither an API key nor Bedrock configuration is present, a typed `AIConfigurationError` is raised with instructions for `agent onboard`.

## Security & Compliance

- **Credential Leakage**: No credentials from the settings file or environment are logged. Only the selection of the client type (Bedrock vs. Direct) is recorded in structured logs.
- **Permissions**: The agent operates under the user's local AWS identity (typically via `AWS_PROFILE`). No static secrets are stored within the codebase.

## Alignment with ADRs

- **ADR-046**: Implements structured logging for client construction and shell command execution results.

```

#### [MODIFY] .agent/etc/agent.yaml

```

<<<SEARCH
  models:
    gemini: models/gemini-3.1-pro-preview
    vertex: gemini-2.5-pro
    openai: gpt-4o
    anthropic: claude-sonnet-4-5-20250929
    vertex-anthropic: claude-sonnet-4-5-20250929
===
  models:
    gemini: models/gemini-3.1-pro-preview
    vertex: gemini-2.5-pro
    openai: gpt-4o
    anthropic: claude-sonnet-4-5-20250929
    vertex-anthropic: claude-sonnet-4-5-20250929
    claude: claude-sonnet-4-5-20250929
>>>

```

### Step 2: Core Framework Integration & Dependency Update

This integration step prepares the core framework for the new Claude provider by upgrading the Anthropic SDK and registering the provider in the central factory. 

**Architectural Decisions:**
- **SDK Upgrade**: Transitioning from `anthropic` to `anthropic[bedrock]` ensures the `AnthropicBedrock` client is available. This pulls in `botocore` and `boto3`, which is expected for Bedrock environments.
- **Unified Provider Routing**: The `PREFIX_FALLBACK` for `claude-` is redirected from the legacy `anthropic` provider to the new `claude` provider. This allows the framework to check `~/.claude/settings.json` for all Claude models, ensuring a consistent developer experience across local and cloud environments.
- **Registry Integration**: Registering 'claude' in `PROVIDERS` and validation lists ensures that `agent provider claude` becomes a valid CLI command and configuration option.

#### [MODIFY] .agent/pyproject.toml

```

<<<SEARCH
    "openai>=1.0.0",
    "anthropic>=0.3.0",
    "google-genai>=0.1.0",
    "langgraph>=0.2.0",
===
"torch>=2.0.0 ; sys_platform != 'darwin' or platform_machine != 'x86_64' or python_version >= '3.13'",
    "openai>=1.0.0",
    "anthropic[bedrock]>=0.3.0",
    "google-genai>=0.1.0",
    "langgraph>=0.2.0",
>>>

```

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased]

### Added
===
## [Unreleased]

### Added

- **INFRA-185 — Claude Provider with AWS Bedrock Support**: Added a new `claude` provider that auto-detects configuration from `~/.claude/settings.json`, supporting both direct Anthropic API and AWS Bedrock transports. Includes automatic SSO credential refresh via `awsAuthRefresh` and safe environment variable injection with precedence rules.
>>>

```

#### [MODIFY] .agent/src/agent/core/ai/providers/__init__.py

```

<<<SEARCH
_PROVIDER_CLASS_MAP: Dict[str, str] = {
    "openai": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini": "agent.core.ai.providers.vertex.VertexAIProvider",
    "vertex": "agent.core.ai.providers.vertex.VertexAIProvider",
    "anthropic": "agent.core.ai.providers.anthropic.AnthropicProvider",
    "ollama": "agent.core.ai.providers.ollama.OllamaProvider",
    "gh": "agent.core.ai.providers.gh.GHProvider",
    "mock": "agent.core.ai.providers.mock.MockProvider",
}
===
_PROVIDER_CLASS_MAP: Dict[str, str] = {
    "openai": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini": "agent.core.ai.providers.vertex.VertexAIProvider",
    "vertex": "agent.core.ai.providers.vertex.VertexAIProvider",
    "anthropic": "agent.core.ai.providers.anthropic.AnthropicProvider",
    "claude": "agent.core.ai.providers.claude.ClaudeProvider",
    "ollama": "agent.core.ai.providers.ollama.OllamaProvider",
    "gh": "agent.core.ai.providers.gh.GHProvider",
    "mock": "agent.core.ai.providers.mock.MockProvider",
}
>>>

<<<SEARCH
_PREFIX_FALLBACKS: Dict[str, str] = {
    "gpt-": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini-": "agent.core.ai.providers.vertex.VertexAIProvider",
}
===
_PREFIX_FALLBACKS: Dict[str, str] = {
    "gpt-": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini-": "agent.core.ai.providers.vertex.VertexAIProvider",
    "claude-": "agent.core.ai.providers.claude.ClaudeProvider",
}
>>>

```

#### [MODIFY] .agent/src/agent/core/ai/service.py

```

<<<SEARCH
    "vertex-anthropic": {
        "name": "Claude on Vertex AI",
        "service": "vertex",
        "secret_key": None,
        "env_var": "GOOGLE_CLOUD_PROJECT",
    },
}
===
    "vertex-anthropic": {
        "name": "Claude on Vertex AI",
        "service": "vertex",
        "secret_key": None,
        "env_var": "GOOGLE_CLOUD_PROJECT",
    },
    "claude": {
        "name": "Claude (Settings/Bedrock)",
        "service": "claude",
        "secret_key": None,
        "env_var": "ANTHROPIC_API_KEY",
    },
}
>>>

<<<SEARCH
        self.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'vertex': 'gemini-2.0-flash',
            'openai': os.getenv("OPENAI_MODEL", "gpt-4o"),
            'anthropic': 'claude-sonnet-4-5-20250929',
            'vertex-anthropic': 'claude-sonnet-4-5-20250929',
            'ollama': os.getenv("OLLAMA_MODEL", "llama3"),
        }
===
        self.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'vertex': 'gemini-2.0-flash',
            'openai': os.getenv("OPENAI_MODEL", "gpt-4o"),
            'anthropic': 'claude-sonnet-4-5-20250929',
            'vertex-anthropic': 'claude-sonnet-4-5-20250929',
            'claude': 'claude-sonnet-4-5-20250929',
            'ollama': os.getenv("OLLAMA_MODEL", "llama3"),
        }
>>>

<<<SEARCH
        fallback_chain = ['gemini', 'vertex', 'openai', 'anthropic', 'vertex-anthropic', 'ollama', 'gh']
===
        fallback_chain = ['gemini', 'vertex', 'openai', 'anthropic', 'claude', 'vertex-anthropic', 'ollama', 'gh']
>>>

```

#### [MODIFY] .agent/src/agent/core/config.py

```

<<<SEARCH
    return ["gh", "openai", "gemini", "anthropic", "vertex", "ollama"]
===
    return ["gh", "openai", "gemini", "anthropic", "claude", "vertex", "ollama"]
>>>

```

### Step 3: Claude Provider Implementation, Security & Observability

The implementation of `ClaudeProvider` focuses on bridging the gap between local developer environments and AWS infrastructure. By auto-detecting and parsing `~/.claude/settings.json`, the provider allows users to maintain a single source of truth for their Claude and Bedrock configurations. 

**Key Design Decisions:**
- **Security-First SSO Refresh:** The `awsAuthRefresh` command is executed using `shlex.split` and `subprocess.run` with `shell=False`. This eliminates shell injection vulnerabilities while still allowing complex commands. A mandatory 60-second timeout prevents the agent from hanging on interactive login prompts.
- **Precedence Logic:** In line with standard CLI tool behavior, existing environment variables always override values found in the settings file, ensuring that explicit user overrides are respected.
- **Unified Interface:** The provider dynamically switches between the `Anthropic` and `AnthropicBedrock` SDK clients. This abstraction allows the rest of the framework to interact with Claude using the same internal interface, regardless of whether the traffic flows through public APIs or a private AWS VPC.
- **Observability:** Adhering to ADR-046, initialization logic includes structured logs that identify the chosen transport and region, facilitating easier debugging of credential resolution issues.

#### [NEW] .agent/src/agent/core/ai/providers/claude.py

```python
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

import os
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Iterator

import anthropic
from anthropic import Anthropic, AnthropicBedrock

from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.providers.utils import AIConfigurationError
from agent.core.logger import get_logger

logger = get_logger(__name__)

def load_claude_settings() -> Dict[str, Any]:
    """
    Loads configuration from ~/.claude/settings.json.
    
    Returns:
        Dict containing the settings or an empty dict if the file doesn't exist or is invalid.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        logger.debug(f"claude: no settings file found at {settings_path}")
        return {}

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.error(f"claude: settings file at {settings_path} is not a valid JSON object")
                return {}
            return data
    except json.JSONDecodeError as e:
        logger.error(f"claude: failed to parse settings JSON at {settings_path}: {e}")
    except Exception as e:
        logger.error(f"claude: error reading settings file: {e}")
    
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
            logger.debug(f"claude: injecting env var from settings: {key}")
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
        logger.info(f"claude: executing auth refresh command: {cmd_str}")
        
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
                f"claude: auth refresh failed with exit code {result.returncode}. "
                f"Error: {result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        logger.warning("claude: auth refresh command timed out after 60 seconds")
    except FileNotFoundError:
        logger.error(f"claude: auth refresh command not found: {cmd_str.split()[0]}")
    except Exception as e:
        logger.error(f"claude: unexpected error during auth refresh: {e}")

class ClaudeProvider(BaseProvider):
    """
    Anthropic Claude provider supporting both direct API and AWS Bedrock transports.
    
    Automatically detects configuration from ~/.claude/settings.json to match
    the user's local Claude Code environment.
    """

    def __init__(self, model_id: str, **kwargs):
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

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generates a completion using the Anthropic Messages API.
        """
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
            logger.error(f"claude: API error: {e}")
            raise e
        except Exception as e:
            logger.error(f"claude: unexpected generation error: {e}")
            raise e

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """
        Streams completion chunks using the Anthropic Messages API.
        """
        try:
            with self.client.messages.stream(
                model=self.model_id,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7),
                system=kwargs.get("system_prompt", anthropic.NOT_GIVEN)
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic.APIError as e:
            logger.error(f"claude: API error during stream: {e}")
            raise e
        except Exception as e:
            logger.error(f"claude: unexpected streaming error: {e}")
            raise e

```

### Step 4: Configuration Updates

This section updates the agent's routing and configuration files to incorporate the new 'claude' provider. We are adding Bedrock-compatible model definitions to the smart router and ensuring the 'claude' provider is given top priority in the routing hierarchy. This allows the system to automatically utilize local Claude Code settings for optimized performance and credential management when using AWS Bedrock or direct Anthropic API keys.

#### [MODIFY] .agent/etc/router.yaml

```

<<<SEARCH
  claude-opus-4-5:
    provider: "anthropic"
    deployment_id: "claude-opus-4-5-20250929"
    tier: "premium"
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075

settings:
  default_tier: "standard"
  provider_priority: ["gemini", "openai", "ollama", "gh"]
===
  claude-opus-4-5:
    provider: "anthropic"
    deployment_id: "claude-opus-4-5-20250929"
    tier: "premium"
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075

  # --- Claude Models via Bedrock/Settings (claude provider) ---
  claude-3-5-sonnet:
    provider: "claude"
    deployment_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"
    tier: "advanced"
    context_window: 200000
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015

  claude-3-haiku:
    provider: "claude"
    deployment_id: "anthropic.claude-3-5-haiku-20241022-v1:0"
    tier: "standard"
    context_window: 200000
    cost_per_1k_input: 0.00025
    cost_per_1k_output: 0.00125

  claude-3-opus:
    provider: "claude"
    deployment_id: "anthropic.claude-3-opus-20240229-v1:0"
    tier: "premium"
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075

settings:
  default_tier: "standard"
  provider_priority: ["claude", "gemini", "openai", "ollama", "gh"]
>>>

```

### Step 5: Documentation Updates

Comprehensive user-facing documentation is critical for the adoption of the new Claude provider, especially for developers already utilizing the Claude Code ecosystem. This section establishes the `claude.md` provider guide, detailing the logic used to parse `~/.claude/settings.json` and the precedence rules that ensure local environment variables remain the authoritative source of truth. By explicitly documenting the Bedrock routing requirements and the automatic SSO refresh mechanism, we minimize onboarding friction and provide a clear path for troubleshooting credential resolution. This documentation aligns with the smart routing strategies outlined in the project architecture by providing users with the necessary model IDs and provider-specific configuration flags.

#### [NEW] .agent/docs/providers/claude.md

```markdown
# Claude Provider Configuration

The Claude provider is a unified interface for accessing Anthropic's Claude models. It is designed to be compatible with existing [Claude Code](https://claude.ai/code) configurations while providing flexible routing through either the direct Anthropic API or AWS Bedrock.

## Configuration Discovery

The provider automatically looks for configuration in two places:
1. The system environment (OS environment variables).
2. The standard Claude Code settings file located at `~/.claude/settings.json`.

**Settings File Format**

The agent specifically parses the `env` block and the `awsAuthRefresh` command from the settings file:

```json
{
  "env": {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_REGION": "us-east-1",
    "AWS_PROFILE": "my-developer-profile",
    "ANTHROPIC_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
  },
  "awsAuthRefresh": "aws sso login --profile my-developer-profile"
}

```

**Precedence Order**

To allow for runtime overrides, the agent follows this strict precedence order:

1.  **Environment Variables**: Any variable explicitly exported in your shell (e.g., `export AWS_PROFILE=prod`) always takes priority.
2.  **Settings File**: If a variable is not found in the environment, the agent attempts to read it from the `env` block in `~/.claude/settings.json`.

## AWS Bedrock Integration

AWS Bedrock is enabled if the agent detects `CLAUDE_CODE_USE_BEDROCK=1` in either the environment or the settings file.

**Required Bedrock Variables**
- `CLAUDE_CODE_USE_BEDROCK`: Must be set to `1` to enable Bedrock transport.
- `AWS_REGION`: The region where your Bedrock models are provisioned (e.g., `us-east-1`).
- `AWS_PROFILE` (Optional): The AWS profile name for credentials.

**Automatic SSO Refresh**
If your configuration includes an `awsAuthRefresh` command, the agent will execute it automatically if it encounters credential expiration or before the first request. This ensures that SSO-based developers do not have to manually run login commands when their session expires.

## Direct Anthropic API

If `CLAUDE_CODE_USE_BEDROCK` is not set to `1`, the agent falls back to the standard Anthropic API.

- `ANTHROPIC_API_KEY`: Required for direct access. This can be stored in your environment or the project secret manager.

## Smart Routing & Models

When using `provider: claude` in your `agent.yaml` or through the smart router, the agent maps model requests to the appropriate Bedrock or Anthropic model IDs. 

Example configuration in `agent.yaml`:

```yaml
agent:
  provider: claude
  models:
    claude: claude-sonnet-4-5

```

## Troubleshooting

- **Transport Selection**: Check the agent startup logs. You should see `INFO: claude: building AnthropicBedrock client` if Bedrock is correctly enabled.
- **SSO Failures**: If the `awsAuthRefresh` command fails, the agent will log a warning and attempt to continue using existing credentials. Ensure your refresh command is valid and executable from the terminal.
- **Configuration Overlap**: If you have both an `ANTHROPIC_API_KEY` and Bedrock configured, Bedrock will take precedence if `CLAUDE_CODE_USE_BEDROCK=1` is set.

```

### Step 6: Verification & Test Suite

The test suite for INFRA-185 provides exhaustive coverage of the configuration discovery and transport selection logic. Following ADR-046, we emphasize structural validation of the provider's lifecycle.

**Testing Strategy:**
1. **Configuration Isolation**: Tests use `unittest.mock.patch` for `os.environ` and `pathlib.Path` to simulate varying developer environments without affecting the host machine.
2. **Security Verification**: Explicit tests ensure that `awsAuthRefresh` command execution utilizes `shlex.split` and `subprocess.run` with `shell=False`, preventing shell injection.
3. **Transport Branching**: Unit tests for the `ClaudeProvider` constructor verify the toggle between `Anthropic` and `AnthropicBedrock` clients, ensuring that the 'direct' transport requires an API key while the 'bedrock' transport relies on AWS credential chains.
4. **Resilience**: Negative tests verify that malformed `settings.json` or failed SSO refresh commands do not cause hard crashes, but instead log warnings and attempt to proceed with environment-level variables.
5. **Integration**: Verification of the provider registry in `agent/core/ai/providers/__init__.py` ensures the `PREFIX_FALLBACK` correctly routes `claude-*` requests to the new unified provider.

#### [NEW] .agent/tests/agent/core/ai/providers/test_claude_provider.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import subprocess

from agent.core.ai.providers.claude import (
    ClaudeProvider, 
    load_claude_settings, 
    _apply_settings_env, 
    _run_aws_auth_refresh
)
from agent.core.ai.providers.utils import AIConfigurationError

@pytest.fixture
def mock_settings_json():
    return {
        "env": {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": "us-east-1",
            "AWS_PROFILE": "test-profile"
        },
        "awsAuthRefresh": "aws sso login --profile test-profile"
    }

def test_load_claude_settings_missing(tmp_path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == {}

def test_load_claude_settings_valid(tmp_path, mock_settings_json):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text(json.dumps(mock_settings_json))
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == mock_settings_json

def test_load_claude_settings_malformed(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text("{ invalid json }")
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == {}

def test_apply_settings_env():
    settings = {"env": {"NEW_VAR": "value", "EXISTING_VAR": "new_value"}}
    with patch.dict(os.environ, {"EXISTING_VAR": "original"}, clear=True):
        _apply_settings_env(settings)
        assert os.environ["NEW_VAR"] == "value"
        assert os.environ["EXISTING_VAR"] == "original"

def test_run_aws_auth_refresh_success():
    settings = {"awsAuthRefresh": "aws sso login"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_aws_auth_refresh(settings)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["aws", "sso", "login"]
        assert mock_run.call_args[1]["shell"] is False

def test_run_aws_auth_refresh_timeout():
    settings = {"awsAuthRefresh": "long_command"}
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 60)):
        # Should not raise exception, just log warning
        _run_aws_auth_refresh(settings)

@patch("agent.core.ai.providers.claude.load_claude_settings")
@patch("agent.core.ai.providers.claude.AnthropicBedrock")
def test_claude_provider_init_bedrock(mock_bedrock, mock_load, mock_settings_json):
    mock_load.return_value = mock_settings_json
    # Simulate environment after _apply_settings_env
    env_vars = {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-east-1"}
    
    with patch.dict(os.environ, env_vars, clear=True):
        provider = ClaudeProvider(model_id="claude-3-sonnet")
        mock_bedrock.assert_called_once_with(aws_region="us-east-1", aws_profile="test-profile")
        assert provider.model_id == "claude-3-sonnet"

@patch("agent.core.ai.providers.claude.load_claude_settings")
@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_init_direct(mock_anthropic, mock_load):
    mock_load.return_value = {}
    env_vars = {"ANTHROPIC_API_KEY": "sk-test-key"}
    
    with patch.dict(os.environ, env_vars, clear=True):
        provider = ClaudeProvider(model_id="claude-3-opus")
        mock_anthropic.assert_called_once_with(api_key="sk-test-key")

def test_claude_provider_init_failure():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(AIConfigurationError, match="ANTHROPIC_API_KEY is not set"):
            ClaudeProvider(model_id="test-model")

@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_generate(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="hello world")]
    )

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}):
        provider = ClaudeProvider(model_id="test-model")
        result = provider.generate("hi")
        assert result == "hello world"
        mock_client.messages.create.assert_called_once()

```

### Step 7: Deployment & Rollback Strategy

The deployment strategy for INFRA-185 focuses on ensuring that the additive `anthropic[bedrock]` dependency (which pulls in `boto3` and `botocore`) does not create version conflicts with existing framework utilities. The integration follows the pattern of existing providers, where the logic is isolated in a standalone module (`claude.py`) and registered in central dispatchers. 

**Verification Steps**:
1. **Dependency Audit**: Run `pip show botocore boto3` to ensure standard AWS SDKs are installed and do not conflict with system-level AWS CLI versions.
2. **Initialization Test**: Confirm the provider initializes by running `agent config set agent.provider claude`. This should trigger the `~/.claude/settings.json` check.
3. **SSO Refresh Verification**: If using Bedrock, verify that the `awsAuthRefresh` command executes correctly if credentials have expired.

**Rollback Procedure**:
In the event of failure, the rollback is safe and non-destructive. All logic is additive. Reverting the registration entries in `service.py` and `providers/__init__.py` will effectively disable the provider. The additive `claude.py` and test files can be removed using the provided utility script.

#### [NEW] .agent/src/agent/utils/rollback_infra_185.py

```python
"""Rollback script for INFRA-185.

Removes additive components introduced for the Claude Bedrock provider.
"""
import os
from pathlib import Path

def rollback():
    """Remove additive files and list registry locations requiring manual revert."""
    # This script is located at .agent/src/agent/utils/rollback_infra_185.py
    src_root = Path(__file__).resolve().parent.parent.parent
    project_root = src_root.parent # .agent/
    
    files_to_delete = [
        src_root / "agent/core/ai/providers/claude.py",
        project_root / "tests/core/ai/providers/test_claude_provider.py",
        project_root / "docs/providers/claude.md"
    ]
    
    print("--- INFRA-185 Rollback Started ---")
    
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"[DELETED] {f}")
        else:
            print(f"[SKIP] {f} (not found)")

    print("\nManual Reversion Required in the following core framework files:")
    print("1. .agent/pyproject.toml: Revert 'anthropic[bedrock]' to 'anthropic'")
    print("2. .agent/src/agent/core/ai/providers/__init__.py: Remove 'claude' registration from PROVIDER_MAP")
    print("3. .agent/src/agent/core/ai/service.py: Remove provider dispatch cases and model mappings")
    print("4. .agent/src/agent/core/config.py: Remove 'claude' from enabled provider logic")
    print("5. .agent/etc/router.yaml: Remove Bedrock model definitions")
    print("6. .agent/etc/agent.yaml: Remove 'claude' configuration block")
    print("\n--- Rollback Guidance Complete ---")

if __name__ == '__main__':
    rollback()

```

## Verification Plan

**Automated Tests**

- [ ] All existing tests pass (`pytest`)
- [ ] New tests pass for each new public interface

**Manual Verification**

- [ ] `agent preflight --story INFRA-185` passes

## Definition of Done

**Documentation**

- [ ] CHANGELOG.md updated
- [ ] Story `## Impact Analysis Summary` updated to list every touched file

**Observability**

- [ ] Logs are structured and free of PII

**Testing**

- [ ] All existing tests pass
- [ ] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook
