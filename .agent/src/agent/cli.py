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

import click
from typing import Optional
from agent.core.ai import ai_service
from agent.core.config import get_valid_providers

# Valid providers will be dynamically retrieved from the configuration.
VALID_PROVIDERS = None

@click.group()
def cli():
    """CLI tool for various AI-related tasks."""
    pass

def validate_provider(ctx: click.Context, param: click.Parameter, value: Optional[str]) -> Optional[str]:
    global VALID_PROVIDERS

    # Lazy load VALID_PROVIDERS from config
    if VALID_PROVIDERS is None:
        VALID_PROVIDERS = get_valid_providers()

    if value:
        provider = value.lower()
        if provider not in VALID_PROVIDERS:
            raise click.BadParameter(f"Invalid provider '{value}'. Supported providers: {', '.join(VALID_PROVIDERS)}")
        return provider
    return None

@click.command()
@click.option("--story", required=True, help="The story for the AI to implement.")
@click.option("--provider", callback=validate_provider, help="Specify the AI provider.")
def implement(story: str, provider: Optional[str] = None):
    """Implement a story using the AI model."""
    try:
        if provider:
            ai_service.set_provider(provider)
        # Note: execute_command is not in core ai_service. 
        # The legacy functional ai_service had it. 
        # Looking at main.py, 'implement' command is actually in agent.commands.implement
        # This cli.py seems to be a secondary entry point or wrapper. 
        # We should call the actual command logic if we can, or implementation logic.
        # But 'execute_command' in the deleted file just printed mock output.
        # If this CLI is used, it expects real behavior.
        # However, purely following the refactor plan to consolidate:
        # We should probably map this to agent.commands.implement.implement which uses typer
        # But this is Click. Mixing them might be messy.
        # Given the instruction was just to fix type hints and duplicate usage:
        
        # We will assume for this task we just want to fix the import and type hints.
        # But wait, ai_service does NOT have execute_command. 
        # I need to verify what execute_command was doing in the file I am deleting.
        # It was: "print(f"Executing '{command}' with provider: {current_provider}.")"
        # So it was a stub.
        
        click.echo(f"Executing 'implement' for story {story} with provider: {ai_service.provider}")
        
    except ValueError as e:
        click.echo(f"Error: {e}")
    except RuntimeError as e:
        click.echo(f"Runtime Error: {e}")

@click.command()
@click.argument("query", required=True)
@click.option("--provider", callback=validate_provider, help="Specify the AI provider.")
def match_story(query: str, provider: Optional[str] = None):
    """Match a story to an existing implementation."""
    try:
        if provider:
            ai_service.set_provider(provider)
        click.echo(f"Executing 'match_story' for query {query} with provider: {ai_service.provider}")
    except ValueError as e:
        click.echo(f"Error: {e}")
    except RuntimeError as e:
        click.echo(f"Runtime Error: {e}")

@click.command()
@click.option("--provider", callback=validate_provider, help="Specify the AI provider.")
def new_runbook(provider: Optional[str] = None):
    """Create a new runbook."""
    try:
        if provider:
            ai_service.set_provider(provider)
        click.echo(f"Executing 'new_runbook' with provider: {ai_service.provider}")
    except ValueError as e:
        click.echo(f"Error: {e}")
    except RuntimeError as e:
        click.echo(f"Runtime Error: {e}")

@click.command()
@click.option("--provider", callback=validate_provider, help="Specify the AI provider.")
def pr(provider: Optional[str] = None):
    """Interact with a pull request."""
    try:
        if provider:
            ai_service.set_provider(provider)
        click.echo(f"Executing 'pr' with provider: {ai_service.provider}")
    except ValueError as e:
        click.echo(f"Error: {e}")
    except RuntimeError as e:
        click.echo(f"Runtime Error: {e}")

cli.add_command(implement)
cli.add_command(match_story)
cli.add_command(new_runbook)
cli.add_command(pr)