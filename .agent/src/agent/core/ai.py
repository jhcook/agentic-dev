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
            'openai': 'gpt-4o'
        }
        
        # 1. Check Gemini
        gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai
                self.clients['gemini'] = genai.Client(api_key=gemini_key)
            except ImportError:
                console.print("[yellow]⚠️  GOOGLE_GEMINI_API_KEY found but 'google-genai' package missing.[/yellow]")

        # 2. Check OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                self.clients['openai'] = OpenAI(api_key=openai_key)
            except ImportError:
                 # Check if installed
                 console.print("[yellow]⚠️  OPENAI_API_KEY found but 'openai' package missing.[/yellow]")

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

    def _set_default_provider(self):
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
        if provider_name in self.clients:
            self.provider = provider_name
            self.is_forced = True
            console.print(f"[bold cyan]🤖 AI Provider set to: {provider_name}[/bold cyan]")
        else:
            console.print(f"[bold red]❌ Provider '{provider_name}' not available/configured.[/bold red]")

    def try_switch_provider(self) -> bool:
        """
        Switches to the next available provider in the chain.
        Returns True if switched, False if no providers left.
        """
        # Chain order: gh -> gemini -> openai
        fallback_chain = ['gh', 'gemini', 'openai']
        
        current_idx = -1
        if self.provider in fallback_chain:
            try:
                current_idx = fallback_chain.index(self.provider)
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
        Sends a completion request. Raises Exception on failure.
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
                    # console.print(f"[dim]⚡ Smart Router selected {model_to_use} ({provider_to_use})[/dim]")
                else:
                    console.print(f"[dim][yellow]⚠️ Smart Router suggested {routed_provider}, but it is not configured. Falling back to default.[/yellow][/dim]")

        if not provider_to_use:
             console.print("[red]❌ No valid AI provider found (Gemini key, OpenAI key, or GH CLI). AI features disabled.[/red]")
             return ""

        # Security / Compliance Warning (Once per call logic?)
        console.print("[dim]🔒 Security Pre-check: Ensuring no PII/Secrets in context...[/dim]")
        # console.print("[yellow]⚠️  remote-inference: Sending data to external AI provider. Do NOT include PII or Secrets.[/yellow]")
        
        try:
            start_time = time.time()
            content = self._try_complete(provider_to_use, system_prompt, user_prompt, model_to_use)
            
            if content:
                logging.info(f"AI Completion Success | Provider: {provider_to_use} | Duration: {time.time() - start_time:.2f}s")
                return content
            else:
                # Should not happen on success, usually implies empty response which is valid but rare
                logging.warning(f"AI Completion Empty | Provider: {provider_to_use}")
                return ""

        except Exception as e:
            logging.error(f"Provider {provider_to_use} failed: {e}")
            raise e # Propagate so caller can handle strategy switch

    def _try_complete(self, provider, system_prompt, user_prompt, model=None) -> str:
        model_used = model or self.models.get(provider)
        
        if provider == "gemini":
            client = self.clients['gemini']
            full_prompt = f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER PROMPT:\n{user_prompt}"
            response = client.models.generate_content(
                model=model_used,
                contents=full_prompt
            )
            return response.text.strip() if response.text else ""

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
            cmd = ["gh", "models", "run", model_used, "--system-prompt", system_prompt]
            max_retries = 3 # "After three errors" (attempts 0, 1, 2)
            for attempt in range(max_retries):
                result = subprocess.run(cmd, input=user_prompt, text=True, capture_output=True)
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
                
            raise Exception("GH Failed to complete")
            
        return ""

ai_service = AIService()
