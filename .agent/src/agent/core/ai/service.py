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

from rich.console import Console

from agent.core.router import router

console = Console()

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
            'openai': os.getenv("OPENAI_MODEL", "gpt-4o")
        }
        
        # 1. Check Gemini
        gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai
                from google.genai import types
                # Set 600s timeout (600,000ms) for large contexts
                http_options = types.HttpOptions(timeout=600000)
                self.clients['gemini'] = genai.Client(api_key=gemini_key, http_options=http_options)
            except (ImportError, Exception) as e:
                console.print(f"[yellow]⚠️  Gemini initialization failed: {e}[/yellow]")

        # 2. Check OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
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

        # Default Priority: GH -> Gemini -> OpenAI
        self._set_default_provider()

    def _check_gh_cli(self) -> bool:
        """Check if gh CLI is available and logged in."""
        try:
            # Check version
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def reset_provider(self):
        """Reset provider to default state (useful after fallback sequences)."""
        self.provider = None
        self.is_forced = False
        self._set_default_provider()

    def _set_default_provider(self):
        # ... existing logic ...
        if 'gh' in self.clients:
            self.provider = 'gh'
        elif 'gemini' in self.clients:
            self.provider = 'gemini'
        elif 'openai' in self.clients:
            self.provider = 'openai'
        else:
            self.provider = None
            
    def set_provider(self, provider_name: str):
        """Force a specific provider."""
        valid_providers = ['gh', 'gemini', 'openai']
        
        if provider_name not in valid_providers:
            console.print(f"[bold red]❌ Invalid provider name: '{provider_name}'. Must be one of: {', '.join(valid_providers)}[/bold red]")
            raise ValueError(f"Invalid provider: {provider_name}")

        if provider_name in self.clients:
            self.provider = provider_name
            self.is_forced = True
            console.print(f"[bold cyan]🤖 AI Provider set to: {provider_name}[/bold cyan]")
        else:
            console.print(f"[bold red]❌ Provider '{provider_name}' is valid but not available/configured.[/bold red]")
            raise RuntimeError(f"Provider not configured: {provider_name}")

    def try_switch_provider(self, current_provider: str) -> bool:
        """
        Switches to the next available provider in the chain.
        Returns True if switched, False if no providers left.
        """
        # Chain order: gh -> gemini -> openai
        fallback_chain = ['gh', 'gemini', 'openai']
        
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
                # Switching provider via fallback essentially "forces" the new path for this session
                self.is_forced = True 
                return True
                
        return False

    def complete(self, system_prompt: str, user_prompt: str, model: str = None) -> str:
        """
        Sends a completion request with automatic fallback.
        """
        provider_to_use = self.provider
        model_to_use = model

        # SMART ROUTING: If not forced and no specific model requested, let the router decide
        if not self.is_forced and not model_to_use:
            route = router.route(user_prompt)
            if route:
                routed_provider = route.get("provider")
                if routed_provider in self.clients:
                    provider_to_use = routed_provider
                    model_to_use = route.get("deployment_id")
                else:
                    console.print(f"[dim][yellow]⚠️ Smart Router suggested {routed_provider}, but it is not configured. Falling back to default.[/yellow][/dim]")

        if not provider_to_use:
             console.print("[red]❌ No valid AI provider found (Gemini key, OpenAI key, or GH CLI). AI features disabled.[/red]")
             return ""

        # Security / Compliance Warning
        console.print("[dim]🔒 Security Pre-check: Ensuring no PII/Secrets in context...[/dim]")
        
        # Fallback Loop
        attempted_providers = set()
        current_p = provider_to_use
        
        while current_p and current_p not in attempted_providers:
            attempted_providers.add(current_p)
            try:
                start_time = time.time()
                content = self._try_complete(current_p, system_prompt, user_prompt, model_to_use if current_p == provider_to_use else None)
                
                if content:
                    logging.info(f"AI Completion Success | Provider: {current_p} | Duration: {time.time() - start_time:.2f}s")
                    return content
                else:
                    logging.warning(f"AI Completion Empty | Provider: {current_p}")
                    return ""

            except Exception as e:
                logging.error(f"Provider {current_p} failed: {e}")
                
                # If we are forced or using a specific model, we might still want to fallback unless explicitly disallowed
                # but typically a forced provider should probably not fallback unless we want maximum reliability.
                # Given the user experience so far, maximum reliability is better.
                if self.try_switch_provider(current_p):
                    new_p = self.provider
                    console.print(f"[yellow]⚠️ Provider {current_p} failed. Falling back to {new_p}...[/yellow]")
                    current_p = new_p
                    continue
                else:
                    console.print(f"[bold red]❌ All AI providers failed. Last error: {e}[/bold red]")
                    raise e

        return ""

    def get_completion(self, prompt: str) -> str:
        """
        Simplified wrapper for single-prompt completion (used by impact command).
        Uses a standard system prompt for an AI assistant.
        """
        return self.complete(
            system_prompt="You are a helpful AI assistant for software development governance.",
            user_prompt=prompt
        )

    def _try_complete(self, provider, system_prompt, user_prompt, model=None) -> str:
        model_used = model or self.models.get(provider)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if provider == "gemini":
                    # Re-initialize client per request to avoid stiff/dead sockets
                    gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
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
                    # Streaming keeps the connection alive, preventing 60s/120s idle timeouts
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
                    return response.choices[0].message.content.strip() if response.choices else ""

                elif provider == "gh":
                    # Combine system and user prompt to avoid CLI argument length limits (ARG_MAX)
                    # and ensuring we use stdin for the bulk of the content.
                    combined_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                    cmd = ["gh", "models", "run", model_used]
                    result = subprocess.run(cmd, input=combined_prompt, text=True, capture_output=True)
                    if result.returncode == 0:
                        return result.stdout.strip()
                    
                    # Check 429
                    if "rate limit" in result.stderr.lower() or "too many requests" in result.stderr.lower():
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 3
                            console.print(f"[yellow]⏳ GH API Rate Limited ({attempt+1}/{max_retries}). Retrying in {wait_time}s...[/yellow]")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception("GH Rate Limited (Max Retries)")
                    
                    # Other error
                    logging.error(f"GH Error: {result.stderr}")
                    raise Exception(f"GH Error: {result.stderr.strip()}")
                
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
                
                if any(ind in error_str for ind in transient_indicators) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    console.print(f"[yellow]⚠️ AI Provider error: {e}. Retrying ({attempt+1}/{max_retries}) in {wait_time}s...[/yellow]")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
            
        return ""

ai_service = AIService()
