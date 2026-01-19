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

import logging
import os
import subprocess
import time
from typing import List, Optional

from prometheus_client import Counter
from rich.console import Console

from agent.core.config import get_valid_providers
from agent.core.router import router
from agent.core.secrets import get_secret

console = Console()

# Prometheus Metrics
ai_command_runs_total = Counter(
    "ai_command_runs_total",
    "Total number of AI command executions",
    ["provider"],
)

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "service": "openai",
        "secret_key": "api_key",
        "env_var": "OPENAI_API_KEY",
    },
    "gemini": {
        "name": "Google Gemini",
        "service": "gemini",
        "secret_key": "api_key",
        "env_var": "GEMINI_API_KEY",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "service": "anthropic",
        "secret_key": "api_key",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "gh": {
        "name": "GitHub CLI",
        "service": "gh",
        "secret_key": None,
        "env_var": None,
    },
}




class AIService:
    """
    Service for interacting with AI providers (GitHub CLI, Gemini, OpenAI).
    
    Handles provider selection, fallback logic, and context management.
    """
    def __init__(self):
        self.provider = None # Current active provider
        self.is_forced = False # Track if provider was explicitly set by user
        self.clients = {}    # configured clients: 'gh', 'gemini', 'openai'
        self.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'openai': os.getenv("OPENAI_MODEL", "gpt-4o"),
            'anthropic': 'claude-sonnet-4-5-20250929'
        }
        
        self.reload()

    def reload(self) -> None:
        """Reloads providers from secrets/env."""
        # 1. Check Gemini
        gemini_key = get_secret("api_key", service="gemini")
        if gemini_key:
            try:
                from google import genai
                from google.genai import types
                # Set 600s timeout (600,000ms) for large contexts
                http_options = types.HttpOptions(timeout=600000)
                self.clients['gemini'] = genai.Client(
                    api_key=gemini_key,
                    http_options=http_options
                )
            except (ImportError, Exception) as e:
                console.print(f"[yellow]⚠️  Gemini initialization failed: {e}[/yellow]")

        # 2. Check OpenAI
        openai_key = get_secret("api_key", service="openai")
        if openai_key:
            try:
                from openai import OpenAI
                # Set 120s timeout
                self.clients['openai'] = OpenAI(api_key=openai_key, timeout=120.0)
            except (ImportError, Exception) as e:
                 console.print(f"[yellow]⚠️  OpenAI initialization failed: {e}[/yellow]")

        # 3. Check GH CLI
        if self._check_gh_cli():
             self.clients['gh'] = "gh-cli" # Marker

        # 4. Check Anthropic
        anthropic_key = get_secret("api_key", service="anthropic")
        if anthropic_key:
            try:
                from anthropic import Anthropic
                # Set 120s timeout for large contexts
                self.clients['anthropic'] = Anthropic(
                    api_key=anthropic_key,
                    timeout=120.0
                )
            except (ImportError, Exception) as e:
                console.print(
                    f"[yellow]⚠️  Anthropic initialization failed: {e}[/yellow]"
                )

        # Default Priority: GH -> Gemini -> OpenAI
        self._set_default_provider()

    def _check_gh_cli(self) -> bool:
        """Check if gh CLI is available and logged in."""
        try:
            # Check version
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
            
            # Check if models extension is installed
            ext_list = subprocess.run(
                ["gh", "extension", "list"], capture_output=True, text=True
            )
            if "gh-models" not in ext_list.stdout:
                console.print("[yellow]📦 Installing 'gh-models' extension...[/yellow]")
                subprocess.run(
                    ["gh", "extension", "install", "https://github.com/github/gh-models"],
                    check=True
                )
            
            return True
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            # If we fail to install the extension, we can't use the provider
            if "extension install" in str(e):
                 console.print(
                     f"[red]❌ Failed to install gh-models extension: {e}[/red]"
                 )
                 return False
            return False

    def reset_provider(self):
        """Reset provider to default state (useful after fallback sequences)."""
        self.provider = None
        self.is_forced = False
        self._set_default_provider()

    def _set_default_provider(self) -> None:
        # 1. Check configured default in agent.yaml
        from agent.core.config import config
        try:
            agent_config = config.load_yaml(config.etc_dir / "agent.yaml")
            configured_provider = config.get_value(agent_config, "agent.provider")
            if configured_provider and configured_provider in self.clients:
                self.provider = configured_provider
                return
        except Exception:
            pass

        # 2. Hardcoded Fallback Priority
        if 'gh' in self.clients:
            self.provider = 'gh'
        elif 'gemini' in self.clients:
            self.provider = 'gemini'
        elif 'openai' in self.clients:
            self.provider = 'openai'
        elif 'anthropic' in self.clients:
            self.provider = 'anthropic'
        else:
            self.provider = None
            
    def set_provider(self, provider_name: str) -> None:
        """Force a specific provider."""
        valid_providers = get_valid_providers()
        
        if provider_name not in valid_providers:
            # Check safely case-insensitive
            found = False
            for vp in valid_providers:
                if vp.lower() == provider_name.lower():
                     provider_name = vp # Canonicalize
                     found = True
                     break
            
            if not found:
                console.print(
                    f"[bold red]❌ Invalid provider name: '{provider_name}'. "
                    f"Must be one of: {', '.join(valid_providers)}[/bold red]"
                )
                raise ValueError(f"Invalid provider: {provider_name}")

        if provider_name in self.clients:
            self.provider = provider_name
            self.is_forced = True
            console.print(
                f"[bold cyan]🤖 AI Provider set to: {provider_name}[/bold cyan]"
            )
        else:
            console.print(
                f"[bold red]❌ Provider '{provider_name}' is valid but not "
                "available/configured.[/bold red]"
            )
            raise RuntimeError(f"Provider not configured: {provider_name}")

    def try_switch_provider(self, current_provider: str) -> bool:
        """
        Switches to the next available provider in the chain.
        Returns True if switched, False if no providers left.
        """
        # Chain order: gh -> gemini -> openai
        # TODO: This chain could also be dynamic from config
        fallback_chain = ['gh', 'gemini', 'openai', 'anthropic']
        
        current_idx = -1
        try:
            current_idx = fallback_chain.index(current_provider)
        except ValueError:
            pass
        
        # Look for next available
        start_search = current_idx + 1
        for i in range(start_search, len(fallback_chain)):
            candidate = fallback_chain[i]
            if candidate in self.clients:
                self.provider = candidate
                # Switching provider via fallback essentially "forces" the
                # new path for this session
                self.is_forced = True 
                return True
                
        return False

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None
    ) -> str:
        """
        Sends a completion request with automatic fallback.
        """
        provider_to_use = self.provider
        model_to_use = model

        # SMART ROUTING: If not forced and no specific model requested,
        # let the router decide
        if not self.is_forced and not model_to_use:
            route = router.route(user_prompt)
            if route:
                routed_provider = route.get("provider")
                if routed_provider in self.clients:
                    provider_to_use = routed_provider
                    model_to_use = route.get("deployment_id")
                else:
                    console.print(
                        f"[dim][yellow]⚠️ Smart Router suggested {routed_provider}, "
                        "but it is not configured. Falling back to default."
                        "[/yellow][/dim]"
                    )

        if not provider_to_use:
             console.print(
                 "[red]❌ No valid AI provider found (Gemini key, OpenAI key, "
                 "or GH CLI). AI features disabled.[/red]"
             )
             return ""

        # Security / Compliance Warning
        console.print(
            "[dim]🔒 Security Pre-check: Ensuring no PII/Secrets in context...[/dim]"
        )
        
        # Fallback Loop
        attempted_providers = set()
        current_p = provider_to_use
        
        while current_p and current_p not in attempted_providers:
            attempted_providers.add(current_p)
            try:
                start_time = time.time()
                
                # OBSERVABILITY: Log start
                logging.info(
                    "AI Request Start",
                    extra={"provider": current_p, "model": model_to_use}
                )
                
                content = self._try_complete(
                    current_p,
                    system_prompt,
                    user_prompt,
                    model_to_use if current_p == provider_to_use else None
                )
                
                duration = time.time() - start_time
                if content:
                    logging.info(
                        f"AI Completion Success | Provider: {current_p} | "
                        f"Duration: {duration:.2f}s"
                    )
                    
                    # METRICS: Increment Counter
                    ai_command_runs_total.labels(provider=current_p).inc()
                    
                    return content
                else:
                    logging.warning(f"AI Completion Empty | Provider: {current_p}")
                    return ""

            except Exception as e:
                logging.error(
                    f"Provider {current_p} failed: {e}",
                    extra={"provider": current_p, "error": str(e)}
                )
                
                # If we are forced or using a specific model, we might still
                # want to fallback unless explicitly disallowed
                # but typically a forced provider should probably not fallback
                # unless we want maximum reliability.
                if self.try_switch_provider(current_p):
                    new_p = self.provider
                    console.print(
                        f"[yellow]⚠️ Provider {current_p} failed. "
                        f"Falling back to {new_p}...[/yellow]"
                    )
                    current_p = new_p
                    continue
                else:
                    console.print(
                        f"[bold red]❌ All AI providers failed. "
                        f"Last error: {e}[/bold red]"
                    )
                    raise e

        return ""

    def get_completion(self, prompt: str) -> str:
        """
        Simplified wrapper for single-prompt completion (used by impact command).
        Uses a standard system prompt for an AI assistant.
        """
        return self.complete(
            system_prompt=(
                "You are a helpful AI assistant for software development governance."
            ),
            user_prompt=prompt
        )

    def get_available_models(self, provider: str | None = None) -> List[dict]:
        """
        Query available models from a provider.
        
        Args:
            provider: The provider to query. If None, uses the current/default provider.
            
        Returns:
            List of dicts with model information: 
            [{"id": "model-id", "name": "display-name"}]
            
        Raises:
            ValueError: If provider is invalid.
            RuntimeError: If provider is not configured.
        """
        target_provider = provider or self.provider
        
        if not target_provider:
            raise RuntimeError(
                "No AI provider available. Configure at least one provider."
            )
        
        valid_providers = get_valid_providers()
        if target_provider not in valid_providers:
            raise ValueError(
                f"Invalid provider: {target_provider}. "
                f"Must be one of: {', '.join(valid_providers)}"
            )
            
        if target_provider not in self.clients:
            raise RuntimeError(
                f"Provider '{target_provider}' is not configured. "
                f"Set the required API key."
            )
        
        models: List[dict] = []
        
        try:
            if target_provider == "gemini":
                client = self.clients['gemini']
                # Use the Gemini models.list() API
                for model in client.models.list():
                    model_id = model.name if hasattr(model, 'name') else str(model)
                    display_name = (
                        model.display_name
                        if hasattr(model, 'display_name')
                        else model_id
                    )
                    models.append({"id": model_id, "name": display_name})
                    
            elif target_provider == "openai":
                client = self.clients['openai']
                # Use the OpenAI models.list() API
                response = client.models.list()
                for model in response.data:
                    model_id = model.id
                    # OpenAI doesn't provide display names, use ID
                    models.append({"id": model_id, "name": model_id})
                    
            elif target_provider == "anthropic":
                # Anthropic doesn't have a models.list() API, return known models
                known_models = [
                    {"id": "claude-sonnet-4-5-20250929", "name": "Claude 4.5 Sonnet"},
                    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
                    {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
                    {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                ]
                models = known_models
                
            elif target_provider == "gh":
                # Use gh models list command
                result = subprocess.run(
                    ["gh", "models", "list"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    # Parse the output (one model per line typically)
                    for line in result.stdout.strip().split("\n"):
                        if line.strip():
                            # gh models list outputs model names directly
                            model_id = line.strip()
                            models.append({"id": model_id, "name": model_id})
                else:
                    raise RuntimeError(
                        f"gh models list failed: {result.stderr.strip()}"
                    )
                    
        except Exception as e:
            logging.error(f"Failed to list models for {target_provider}: {e}")
            raise RuntimeError(f"Failed to list models for {target_provider}: {e}")
            
        return models

    def _try_complete(
        self,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None
    ) -> str:
        model_used = model or self.models.get(provider)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if provider == "gemini":
                    # Re-initialize client per request to avoid stiff/dead sockets
                    gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv(
                        "GEMINI_API_KEY"
                    )
                    from google import genai
                    from google.genai import types
                    
                    bg_client = genai.Client(
                        api_key=gemini_key, 
                        http_options=types.HttpOptions(timeout=600000)
                    )
                    
                    config = types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        http_options=types.HttpOptions(timeout=600000),
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                    response_stream = bg_client.models.generate_content_stream(
                        model=model_used,
                        contents=user_prompt,
                        config=config
                    )
                    
                    full_text = ""
                    # Streaming keeps the connection alive,
                    # preventing 60s/120s idle timeouts
                    for chunk in response_stream:
                        if chunk.text:
                            full_text += chunk.text
                            
                    return full_text.strip()

                elif provider == "openai":
                    client = self.clients['openai']
                    response = client.chat.completions.create(
                        model=model_used,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    )
                    if response.choices:
                        return response.choices[0].message.content.strip()
                    return ""

                elif provider == "gh":
                    # Combine system and user prompt to avoid CLI argument length limits
                    # (ARG_MAX) and ensuring we use stdin for the bulk of the content.
                    combined_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                    cmd = ["gh", "models", "run", model_used]
                    result = subprocess.run(
                        cmd, input=combined_prompt, text=True, capture_output=True
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                    
                    # Check 429
                    err = result.stderr.lower()
                    if "rate limit" in err or "too many requests" in err:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 3
                            console.print(
                        f"[yellow]⏳ GH API Rate Limited ({attempt+1}/{max_retries}). "
                        f"Retrying in {wait_time}s...[/yellow]"
                    )
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception("GH Rate Limited (Max Retries)")
                            
                    # Start of Upgrade Logic Check
                    # If it's a generic failure, it might be an outdated extension. 
                    # Try upgrading ONCE per call.
                    # We can use a flag or check if we haven't retried yet.
                    # For simplicity, if we haven't exhausted retries, try upgrading.
                    if attempt == 0:
                         # Only try upgrade on the very first failure of a request
                         console.print(
                             "[yellow]🔄 GH Model run failed. "
                             "Attempting extension upgrade...[/yellow]"
                         )
                         try:
                             subprocess.run(
                                 ["gh", "extension", "upgrade", "github/gh-models"], 
                                 check=True, 
                                 capture_output=True
                             )
                             # Retry immediately without sleep
                             continue 
                         except Exception as upgrade_err:
                             console.print(f"[dim]Upgrade failed: {upgrade_err}[/dim]")
                    
                    # Other error
                    logging.error(f"GH Error: {result.stderr}")
                    raise Exception(f"GH Error: {result.stderr.strip()}")

                elif provider == "anthropic":
                    client = self.clients['anthropic']
                    full_text = ""
                    # Use streaming to prevent timeouts with large contexts
                    # (similar to Gemini)
                    with client.messages.stream(
                        model=model_used,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_prompt}
                        ]
                    ) as stream:
                        for text in stream.text_stream:
                            full_text += text
                    return full_text.strip()
                
            except Exception as e:
                # Catch transient network errors and retry
                error_str = str(e).lower()
                transient_indicators = [
                    "remote protocol error", 
                    "server disconnected", 
                    "timeout", 
                    "connection reset",
                    "rate limit",
                    "dns resolution"
                ]
                
                if (
                    any(ind in error_str for ind in transient_indicators)
                    and attempt < max_retries - 1
                ):
                    wait_time = (attempt + 1) * 2
                    console.print(
                        f"[yellow]⚠️ AI Provider error: {e}. "
                        f"Retrying ({attempt+1}/{max_retries}) "
                        f"in {wait_time}s...[/yellow]"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
            
        return ""

ai_service = AIService()
