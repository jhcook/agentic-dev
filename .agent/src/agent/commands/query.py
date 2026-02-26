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

"""
Agent query command - Ask natural language questions about the codebase.

Uses a RAG (Retrieval-Augmented Generation) pattern to find relevant
code and documentation, then synthesizes an answer with citations.
"""

import asyncio
import logging
import subprocess
from pathlib import Path

import typer
from rich.console import Console

# from agent.core.ai import ai_service # Moved to local imports
from agent.core.context_builder import ContextBuilder

logger = logging.getLogger(__name__)
console = Console()


SYSTEM_PROMPT = """You are a helpful AI assistant for software developers.
Answer the user's question based *only* on the provided context from the codebase.

The context consists of multiple file snippets, each marked with `--- START filepath ---` and `--- END filepath ---`.

When you use information from a file, you MUST cite it at the end of your answer like this: [Source: filepath].

If the context does not contain the answer, state that you cannot answer the question with the given information. Do not make things up.

Keep your answers concise and focused on the question asked."""


async def run_query(query: str, root_dir: Path) -> str:
    """
    Execute a RAG query against the codebase.
    
    Args:
        query: The user's question.
        root_dir: Repository root directory.
        
    Returns:
        The AI-generated answer with citations.
    """
    console.print("[dim]🔍 Finding relevant context...[/dim]")
    
    context_builder = ContextBuilder(root_dir)
    context = await context_builder.build_context(query)
    
    if not context.strip():
        return "I couldn't find any relevant files in the repository to answer your question. Please try rephrasing or using different keywords."
    
    console.print("[dim]🧠 Synthesizing answer with AI...[/dim]")
    
    user_prompt = f"""CONTEXT:
{context}

QUESTION:
{query}"""
    
    from agent.core.ai import ai_service  # ADR-025: lazy init
    response = ai_service.complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt
    )
    return response


def grep_fallback(query: str) -> None:
    """Fall back to simple grep search when AI is not available."""
    console.print("[yellow]AI features not configured. Falling back to grep search:[/yellow]\n")
    
    from agent.core.config import config
    context_builder = ContextBuilder(config.repo_root)
    
    search_dirs = [str(d) for d in context_builder.search_dirs]
    existing_dirs = [d for d in search_dirs if Path(d).resolve().exists()]
    
    if not existing_dirs:
        console.print("[red]No searchable directories found.[/red]")
        return
        
    import re
    stopwords = {"how", "what", "where", "why", "when", "who", "do", "i", "is", "a", "an", "the", "in", "on", "at", "to", "for", "with", "about", "can", "you", "does", "did", "of"}
    words = re.findall(r'\b\w+\b', query.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    pattern = "|".join(keywords[:5]) if keywords else query
    
    try:
        subprocess.run(
            ['grep', '-rniE', '--color=always', pattern] + existing_dirs,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        console.print("[red]Search timed out.[/red]")
    except FileNotFoundError:
        console.print("[red]grep not found. Please install grep.[/red]")


def query(
    text: str = typer.Argument(..., help="The question to ask about the codebase."),
    offline: bool = typer.Option(False, "--offline", help="Use grep fallback instead of AI."),
):
    """
    Ask a natural language question about the codebase.
    
    Uses AI to find relevant code and documentation, then synthesizes
    an answer with citations to source files.
    
    Examples:
        agent query "how do I create a new workflow?"
        agent query "where is the AI service defined?"
        agent query "what does the implement command do?"
    """
    # Check if AI is available
    from agent.core.ai import ai_service  # ADR-025: lazy init
    
    if not offline:
        try:
            ai_service._ensure_initialized()
        except Exception as e:
            console.print(f"[yellow]⚠️  Failed to initialize AI service: {e}[/yellow]")
            
    if offline or ai_service.provider is None:
        if not offline:
            console.print("[yellow]⚠️  No AI provider configured.[/yellow]")
            console.print("[dim]Set GEMINI_API_KEY or OPENAI_API_KEY, or use --offline for grep.[/dim]\n")
        grep_fallback(text)
        return
    
    try:
        from agent.core.config import config
        answer = asyncio.run(run_query(text, config.repo_root))
        
        console.print("\n[bold green]✅ Answer:[/bold green]\n")
        console.print(answer)
        
    except Exception as e:
        console.print(f"[red]❌ Query failed: {e}[/red]")
        console.print("\n[dim]Falling back to grep search...[/dim]\n")
        grep_fallback(text)