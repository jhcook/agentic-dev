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
import sys
import time
from typing import List, Optional
import warnings

from prometheus_client import Counter, Histogram
from rich.console import Console

# --- Suppress verbose AI / Embedding Library Logging ---
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

warnings.filterwarnings("ignore", module="huggingface_hub.*")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
logging.getLogger("backoff").setLevel(logging.ERROR)

from agent.core.config import get_valid_providers
from agent.core.router import router
from agent.core.secrets import get_secret

console = Console()

ai_command_runs_total = Counter(
    "ai_command_runs_total",
    "Total number of AI command executions",
    ["provider"],
)
ai_completion_latency = Histogram(
    "ai_completion_latency_seconds",
    "Latency of AI completion calls in seconds",
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
    "vertex": {
        "name": "Google Vertex AI",
        "service": "vertex",
        "secret_key": "api_key",
        "env_var": "GOOGLE_CLOUD_PROJECT",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "service": "ollama",
        "secret_key": None,
        "env_var": "OLLAMA_HOST",
    },
}




class AIService:
    """
    Service for interacting with AI providers (GitHub CLI, Gemini, Vertex AI, OpenAI).
    
    Handles provider selection, fallback logic, and context management.
    """
    def __init__(self):
        self.provider = None # Current active provider
        self.is_forced = False # Track if provider was explicitly set by user
        self.clients = {}    # configured clients: 'gh', 'gemini', 'openai'
        self.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'vertex': 'gemini-2.0-flash',
            'openai': os.getenv("OPENAI_MODEL", "gpt-4o"),
            'anthropic': 'claude-sonnet-4-5-20250929',
            'ollama': os.getenv("OLLAMA_MODEL", "llama3"),
        }
        
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy load providers if not already done."""
        if not self._initialized:
            # Governance Recommendation: Validate credentials at service level
            # so strict boundaries are respected (Core doesn't rely on CLI).
            from agent.core.auth.credentials import validate_credentials
            from agent.core.secrets import SecretManagerError

            try:
                validate_credentials(check_llm=True)
            except SecretManagerError as e:
                # CONFIGURATION: If secrets are locked, offer to unlock them interactively
                # This aligns with the "Helpful Agent" persona
                console.print(f"[yellow]🔐 {e}[/yellow]")
                
                # We can't easily import 'Confirm' here if not already imported, 
                # but we use rich.prompt at module level or import inside.
                from rich.prompt import Confirm
                
                # Only prompt if we are in an interactive session
                if sys.stdout.isatty():
                    if Confirm.ask("Would you like to unlock the Secret Manager now?"):
                        # Run the login command interactively
                        try:
                            subprocess.run([sys.executable, "-m", "agent.main", "secret", "login"], check=True)
                            # Retry validation after unlock
                            validate_credentials(check_llm=True)
                        except subprocess.CalledProcessError:
                            console.print("[red]❌ Unlock failed. AI features may be limited.[/red]")
                            raise e
                    else:
                        raise e
                else:
                    raise e
            
            self.reload()
            self._initialized = True

    @staticmethod
    def _build_genai_client(provider: str) -> "genai.Client":
        """Factory for google-genai Client construction.

        Builds a ``genai.Client`` configured for either Gemini (API-key auth)
        or Vertex AI (Application Default Credentials).  Both providers use
        the same SDK; only the authentication mechanism differs.

        Args:
            provider: ``"gemini"`` or ``"vertex"``.

        Returns:
            A configured ``genai.Client`` instance.

        Raises:
            ImportError: If ``google-genai`` is not installed.
            ValueError: If *provider* is not ``"gemini"`` or ``"vertex"``.
        """
        from google import genai
        from google.genai import types

        timeout_ms = int(os.environ.get("AGENT_AI_TIMEOUT_MS", 120000))
        http_options = types.HttpOptions(timeout=timeout_ms)

        if provider == "gemini":
            api_key = get_secret("api_key", service="gemini")
            return genai.Client(api_key=api_key, http_options=http_options)

        if provider == "vertex":
            project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            logging.debug(
                "Vertex AI client: project=%s, location=%s", project, location
            )
            return genai.Client(
                vertexai=True,
                project=project,
                location=location,
                http_options=http_options,
            )

        raise ValueError(f"Unsupported genai provider: {provider}")

    def reload(self) -> None:
        """Reloads providers from secrets/env."""
        # 1. Check Gemini
        gemini_key = get_secret("api_key", service="gemini")
        if gemini_key:
            try:
                self.clients['gemini'] = self._build_genai_client("gemini")
                logging.debug("Gemini provider initialized from secrets.")
            except ImportError:
                console.print(
                    "[dim]ℹ️  Gemini key found but google-genai package not installed. "
                    "Install with: pip install google-genai[/dim]"
                )
            except Exception as e:
                console.print(f"[yellow]⚠️  Gemini initialization failed: {e}[/yellow]")
        else:
            logging.debug("Skipping Gemini: GEMINI_API_KEY not found in environment or secrets.")

        # 2. Check Vertex AI
        vertex_proj = os.getenv("GOOGLE_CLOUD_PROJECT") or get_secret("api_key", service="vertex")
        if vertex_proj:
            # Set the env var so _build_genai_client finds it natively
            os.environ["GOOGLE_CLOUD_PROJECT"] = vertex_proj
            try:
                self.clients['vertex'] = self._build_genai_client("vertex")
                logging.debug(
                    "Vertex AI provider initialized (project=%s)",
                    vertex_proj,
                )
            except ImportError:
                console.print(
                    "[dim]ℹ️  GOOGLE_CLOUD_PROJECT set but google-genai package not installed. "
                    "Install with: pip install google-genai[/dim]"
                )
            except Exception as e:
                # Provide a helpful hint if it's an ADC auth issue
                if "DefaultCredentialsError" in str(getattr(e, '__class__', '')) or "default credentials" in str(e).lower():
                    console.print("[yellow]⚠️  Vertex AI authentication missing (DefaultCredentialsError).[/yellow]")
                    console.print("[yellow]   Please run: gcloud auth application-default login[/yellow]")
                else:
                    console.print(f"[yellow]⚠️  Vertex AI initialization failed: {e}[/yellow]")
        else:
            logging.debug("Skipping Vertex AI: GOOGLE_CLOUD_PROJECT not found in environment or secrets.")

        # 3. Check OpenAI
        openai_key = get_secret("api_key", service="openai")
        if openai_key:
            try:
                from openai import OpenAI
                # Set 120s timeout
                self.clients['openai'] = OpenAI(api_key=openai_key, timeout=120.0)
                logging.debug("OpenAI provider initialized from secrets.")
            except ImportError:
                console.print(
                    "[dim]ℹ️  OpenAI key found but openai package not installed. "
                    "Install with: pip install openai[/dim]"
                )
            except Exception as e:
                console.print(f"[yellow]⚠️  OpenAI initialization failed: {e}[/yellow]")
        else:
            logging.debug("Skipping OpenAI: OPENAI_API_KEY not found in environment or secrets.")

        # 4. Check GH CLI
        if self._check_gh_cli():
             self.clients['gh'] = "gh-cli" # Marker
             logging.debug("GH provider initialized via local CLI installation.")
        else:
             logging.debug("Skipping GH provider: Local CLI not installed or missing models extension.")

        # 5. Check Anthropic
        anthropic_key = get_secret("api_key", service="anthropic")
        if anthropic_key:
            try:
                from anthropic import Anthropic
                # Set 120s timeout for large contexts
                self.clients['anthropic'] = Anthropic(
                    api_key=anthropic_key,
                    timeout=120.0
                )
                logging.debug("Anthropic provider initialized from secrets.")
            except ImportError:
                console.print(
                    "[dim]ℹ️  Anthropic key found but anthropic package not installed. "
                    "Install with: pip install anthropic[/dim]"
                )
            except Exception as e:
                console.print(
                    f"[yellow]⚠️  Anthropic initialization failed: {e}[/yellow]"
                )
        else:
            logging.debug("Skipping Anthropic: ANTHROPIC_API_KEY not found in environment or secrets.")

        # 6. Check Ollama (Self-hosted, no API key required)
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        # @Security: Guard against remote Ollama hosts to prevent data exfiltration
        from urllib.parse import urlparse
        parsed = urlparse(ollama_host)
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1", None):
            logging.warning(
                "OLLAMA_HOST=%s is not localhost — skipping for security.",
                ollama_host,
            )
        else:
            try:
                import httpx
                resp = httpx.get(f"{ollama_host}/", timeout=2.0)
                if resp.status_code == 200:
                    from openai import OpenAI
                    self.clients['ollama'] = OpenAI(
                        base_url=f"{ollama_host}/v1",
                        api_key="ollama",  # Dummy — Ollama ignores this but SDK requires it
                        timeout=120.0,
                    )
                    logging.info("Ollama provider initialized at %s", ollama_host)
                else:
                    logging.info("Ollama health check failed (status %s)", resp.status_code)
            except Exception:
                logging.debug("Skipping Ollama: not reachable at %s", ollama_host)

        # Default Priority: GH -> Gemini -> Vertex -> OpenAI -> Anthropic -> Ollama
        self._set_default_provider()

    def _check_gh_cli(self) -> bool:
        """Check if gh CLI is available and logged in."""
        try:
            # Check version
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
            
            # Check auth status (fails if not logged in)
            auth_check = subprocess.run(
                ["gh", "auth", "status"], 
                capture_output=True, 
                text=True
            )
            if auth_check.returncode != 0:
                # Not logged in, so we can't use GH provider
                # Does not print error, just returns False so we skip it in auto-detection
                # But if forced, it might be an issue. 
                # For lazy-load, we just silently skip adding it to clients.
                return False

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
        # If the provider was forced (e.g. via CLI arg), do not overwrite it
        # with default logic during lazy initialization.
        if self.is_forced and self.provider:
            return

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
        elif 'vertex' in self.clients:
            self.provider = 'vertex'
        elif 'openai' in self.clients:
            self.provider = 'openai'
        elif 'anthropic' in self.clients:
            self.provider = 'anthropic'
        elif 'ollama' in self.clients:
            self.provider = 'ollama'
        else:
            self.provider = None
            
    def set_provider(self, provider_name: str) -> None:
        """
        Force a specific provider.
        
        Note: This does NOT strictly validate credential existence at this stage,
        adhering to ADR-025 (Lazy Initialization). Validation occurs on first usage.
        """
        valid_providers = get_valid_providers()
        
        # Normalize
        provider_match = None
        for vp in valid_providers:
             if vp.lower() == provider_name.lower():
                 provider_match = vp
                 break
                 
        if not provider_match:
            console.print(
                f"[bold red]❌ Invalid provider name: '{provider_name}'. "
                f"Must be one of: {', '.join(valid_providers)}[/bold red]"
            )
            # Use ValueError for bad input
            raise ValueError(f"Invalid provider: {provider_name}")

        self.provider = provider_match
        self.is_forced = True
        console.print(
            f"[bold cyan]🤖 AI Provider selected: {provider_match}[/bold cyan]"
        )

    def try_switch_provider(self, current_provider: str) -> bool:
        """
        Switches to the next available provider in the chain.
        Returns True if switched, False if no providers left.
        """
        # Chain order: gh -> gemini -> vertex -> openai -> anthropic -> ollama
        # TODO: This chain could also be dynamic from config
        fallback_chain = ['gh', 'gemini', 'vertex', 'openai', 'anthropic', 'ollama']
        
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
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Sends a completion request with automatic fallback.

        Args:
            system_prompt: System-level instruction for the AI model.
            user_prompt: The user query or content to process.
            model: Optional specific model deployment ID to use.
            temperature: Optional float controlling response randomness.
                Use 0.0 for deterministic output (e.g. governance checks).
                If None, uses each provider's default.
        """
        self._ensure_initialized()
        
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
                
                # OBSERVABILITY: OTel span + log start
                try:
                    from opentelemetry import trace as _otel_trace
                    _tracer = _otel_trace.get_tracer(__name__)
                except ImportError:
                    _tracer = None

                import contextlib
                _span_ctx = _tracer.start_as_current_span("ai.completion") if _tracer else contextlib.nullcontext()
                with _span_ctx as span:
                    if span is not None and hasattr(span, "set_attribute"):
                        span.set_attribute("ai.provider", current_p)
                        span.set_attribute("ai.model", model_to_use or "")
                    
                    logging.info(
                        "AI Request Start",
                        extra={"provider": current_p, "model": model_to_use}
                    )
                    
                    content = self._try_complete(
                        current_p,
                        system_prompt,
                        user_prompt,
                        model_to_use if current_p == provider_to_use else None,
                        temperature=temperature
                    )
                
                duration = time.time() - start_time
                if content:
                    logging.info(
                        f"AI Completion Success | Provider: {current_p} | "
                        f"Duration: {duration:.2f}s"
                    )
                    
                    # METRICS: Increment Counter + Latency Histogram
                    ai_command_runs_total.labels(provider=current_p).inc()
                    ai_completion_latency.labels(provider=current_p).observe(duration)
                    
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
        self._ensure_initialized()
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
            if target_provider in ("gemini", "vertex"):
                client = self.clients[target_provider]
                # Use the genai models.list() API (works for both Gemini and Vertex)
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
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        model_used = model or self.models.get(provider)
        from agent.core.config import config as _cfg
        max_retries = max(3, _cfg.panel_num_retries)
        
        for attempt in range(max_retries):
            try:
                if provider in ("gemini", "vertex"):
                    # Re-initialize client per request to avoid stiff/dead sockets
                    from google.genai import types

                    bg_client = self._build_genai_client(provider)
                    
                    timeout_ms = int(os.environ.get("AGENT_AI_TIMEOUT_MS", 120000))
                    gen_config_kwargs = {
                        "system_instruction": system_prompt,
                        "http_options": types.HttpOptions(timeout=timeout_ms),
                        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
                    }
                    if temperature is not None:
                        gen_config_kwargs["temperature"] = temperature
                    config = types.GenerateContentConfig(**gen_config_kwargs)
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
                    create_kwargs = {
                        "model": model_used,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                    }
                    if temperature is not None:
                        create_kwargs["temperature"] = temperature
                    response = client.chat.completions.create(**create_kwargs)
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
                    
                    # Check 429 or Context Limit
                    err = result.stderr.lower()
                    
                    # Context Limit / Payload Too Large
                    if "too large" in err or "413" in err or "context length" in err:
                        console.print(
                            f"[red]❌ GH Models Context Limit Exceeded. "
                            f"The prompt is too large for the 'gh' provider (approx 8k tokens). "
                            f"Please use Gemini or OpenAI for larger tasks.[/red]"
                        )
                        # Do not retry context errors, they won't succeed
                        raise Exception("GH Context Limit Exceeded")

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
                    stream_kwargs = {
                        "model": model_used,
                        "max_tokens": 4096,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ],
                    }
                    if temperature is not None:
                        stream_kwargs["temperature"] = temperature
                    with client.messages.stream(**stream_kwargs) as stream:
                        for text in stream.text_stream:
                            full_text += text
                    return full_text.strip()

                elif provider == "ollama":
                    # Ollama uses the OpenAI-compatible API
                    client = self.clients['ollama']
                    ollama_kwargs = {
                        "model": model_used,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                    }
                    if temperature is not None:
                        ollama_kwargs["temperature"] = temperature
                    response = client.chat.completions.create(**ollama_kwargs)
                    if response.choices:
                        content = response.choices[0].message.content
                        return content.strip() if content else ""
                    return ""
                
            except Exception as e:
                # Catch-all is necessary because different provider SDKs (Google, OpenAI, Anthropic) 
                # raise different base exceptions. We inspect specific errors below.
                
                # Check for SSL errors first - Fail Fast if Proxy/Cert issue
                from agent.core.net_utils import check_ssl_error
                
                # Map providers to their API endpoints for better debugging
                host_map = {
                    "openai": "api.openai.com",
                    "gemini": "generativelanguage.googleapis.com",
                    "vertex": "us-central1-aiplatform.googleapis.com",
                    "anthropic": "api.anthropic.com", 
                    "gh": "models.github.com",
                    "ollama": "localhost:11434",
                }
                target_host = host_map.get(provider, f"Provider: {provider}")
                
                ssl_msg = check_ssl_error(e, url=target_host)
                if ssl_msg:
                    logging.error(f"SSL Error: {ssl_msg}")
                    # Do not retry SSL errors, they are configuration issues
                    raise e
                    
                # Check for fatal proxy/connection errors FIRST
                error_str = str(e).lower()
                if any(ind in error_str for ind in ["certificate_verify", "ssl", "deadline_exceeded", "504"]):
                    # If corporate proxy killed the proxy prematurely, abort
                    raise e
                    
                # Catch transient network errors and retry
                transient_indicators = [
                    "remote protocol error",  
                    "server disconnected", 
                    "timeout", 
                    "connection reset",
                    "rate limit",
                    "dns resolution",
                    "429",
                    "resource exhausted",
                    "503",
                    "unavailable",
                    "high demand",
                ]
                
                if (
                    any(ind in error_str for ind in transient_indicators)
                    and attempt < max_retries - 1
                ):
                    # Treat 503/unavailable/high-demand same as rate-limit
                    rate_limit_indicators = [
                        "429", "rate limit", "resource exhausted",
                        "503", "unavailable", "high demand",
                    ]
                    if any(ind in error_str for ind in rate_limit_indicators):
                         rate_limit_max = _cfg.panel_num_retries
                         if attempt < rate_limit_max - 1:
                             # Base 5s, then 10s, 20s, up to 60s
                             wait_time = min(5 * (2 ** attempt), 60)
                             console.print(
                                 f"[yellow]⚠️ Rate limit ({provider}). "
                                 f"Backoff retry {attempt+1}/{rate_limit_max} "
                                 f"in {wait_time}s...[/yellow]"
                             )
                             time.sleep(wait_time)
                             continue
                         else:
                             console.print(
                                 f"[yellow]⚠️ Rate limit ({provider}). "
                                 f"Exhausted {rate_limit_max} retries, "
                                 f"switching providers...[/yellow]"
                             )
                             raise e
                    
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

def get_embeddings_model() -> "HuggingFaceEmbeddings":
    """
    Returns a configured document embedding model for vector search.
    Defaults to all-MiniLM-L6-v2 via sentence-transformers for local fast embedding.
    """
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

ai_service = AIService()
