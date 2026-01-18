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
Context builder for RAG-based codebase queries.

Finds relevant files, reads and scrubs content, and builds context
for LLM queries while respecting .gitignore and token budgets.
"""

import asyncio
import subprocess
import logging
from pathlib import Path
from typing import List, Set

from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)

MAX_FILE_TOKENS = 4096
CONTEXT_TOKEN_BUDGET = 8192

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4


class ContextBuilder:
    """
    Builds context from local repository files for RAG queries.
    
    Respects .gitignore patterns, scrubs PII, and manages token budgets.
    """
    
    def __init__(self, root_dir: Path):
        """
        Initialize context builder.
        
        Args:
            root_dir: Root directory of the repository.
        """
        self.root_dir = Path(root_dir).resolve()
        self.ignore_patterns = self._load_gitignore()
    
    def _load_gitignore(self) -> Set[str]:
        """Load and parse .gitignore patterns."""
        patterns = {
            ".git/", ".git", 
            "*.pyc", "__pycache__/", 
            "node_modules/",
            ".venv/", "venv/",
            "*.egg-info/",
            ".agent/cache/",
            ".agent/secrets/"
        }
        
        # Load project .gitignore
        gitignore_path = self.root_dir / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.add(line)
            except Exception as e:
                logger.warning(f"Could not read .gitignore: {e}")
        
        # Also load .agentignore if present
        agentignore_path = self.root_dir / ".agentignore"
        if agentignore_path.exists():
            try:
                with open(agentignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.add(line)
            except Exception as e:
                logger.warning(f"Could not read .agentignore: {e}")
        
        return patterns
    
    def _is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        path_str = str(path)
        
        for pattern in self.ignore_patterns:
            # Simple pattern matching
            if pattern.endswith('/'):
                # Directory pattern
                if pattern.rstrip('/') in path_str:
                    return True
            elif pattern.startswith('*'):
                # Extension pattern
                if path_str.endswith(pattern[1:]):
                    return True
            else:
                # Exact or substring match
                if pattern in path_str:
                    return True
        
        return False
    
    def _is_binary_file(self, path: Path) -> bool:
        """Check if a file is binary."""
        binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
            '.pdf', '.zip', '.tar', '.gz', '.bz2',
            '.exe', '.dll', '.so', '.dylib',
            '.pyc', '.pyo', '.whl',
            '.db', '.sqlite', '.sqlite3',
            '.woff', '.woff2', '.ttf', '.eot',
        }
        return path.suffix.lower() in binary_extensions
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // CHARS_PER_TOKEN
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximate token limit."""
        max_chars = max_tokens * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        # Try to truncate at a line boundary
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * 0.8:
            truncated = truncated[:last_newline]
        
        return truncated + "\n... [truncated]"
    
    async def _find_relevant_files(self, query: str) -> List[Path]:
        """
        Find files containing query terms using grep.
        
        Args:
            query: Search query string.
            
        Returns:
            List of file paths matching the query.
        """
        # Search directories
        search_dirs = [
            self.root_dir / "docs",
            self.root_dir / ".agent" / "workflows",
            self.root_dir / ".agent" / "src" / "agent",
            self.root_dir / ".agent" / "rules",
        ]
        
        # Add README if exists
        readme = self.root_dir / "README.md"
        if readme.exists():
            search_dirs.append(readme)
        
        # Filter to existing paths
        existing_dirs = [str(d) for d in search_dirs if d.exists()]
        
        if not existing_dirs:
            logger.warning("No search directories found")
            return []
        
        # Use grep for fast search (case-insensitive, files only)
        try:
            cmd = ['grep', '-ril', '--include=*.py', '--include=*.md', 
                   '--include=*.yaml', '--include=*.yml', '--include=*.txt',
                   query] + existing_dirs
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode is not None and proc.returncode > 1:
                # grep error
                logger.warning(f"grep error: {stderr.decode()}")
                return []
            
            found_files = []
            for line in stdout.decode().strip().split('\n'):
                if line:
                    path = Path(line)
                    if not self._is_ignored(path) and not self._is_binary_file(path):
                        found_files.append(path)
            
            return found_files[:20]  # Limit to 20 files
            
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []
    
    def _read_and_scrub_file(self, file_path: Path) -> str:
        """
        Read a file and scrub it for PII (synchronous).
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Scrubbed file content with markers, or empty string on error.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Truncate if too large
            if self._estimate_tokens(content) > MAX_FILE_TOKENS:
                content = self._truncate_to_tokens(content, MAX_FILE_TOKENS)
            
            # Scrub PII
            scrubbed = scrub_sensitive_data(content)
            
            # Format with file markers
            rel_path = file_path
            try:
                rel_path = file_path.relative_to(self.root_dir)
            except ValueError:
                pass
            
            return f"--- START {rel_path} ---\n{scrubbed}\n--- END {rel_path} ---\n"
            
        except UnicodeDecodeError:
            logger.debug(f"Skipping binary file: {file_path}")
            return ""
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return ""
    
    async def build_context(self, query: str) -> str:
        """
        Build context for a query by finding and reading relevant files.
        
        Args:
            query: The user's search query.
            
        Returns:
            Assembled context string within token budget.
        """
        relevant_files = await self._find_relevant_files(query)
        
        if not relevant_files:
            logger.info("No relevant files found for query")
            return ""
        
        logger.info(f"Found {len(relevant_files)} relevant files")
        
        # Read and assemble context
        context_parts = []
        total_tokens = 0
        
        for file_path in relevant_files:
            content = self._read_and_scrub_file(file_path)
            if content:
                content_tokens = self._estimate_tokens(content)
                
                if total_tokens + content_tokens <= CONTEXT_TOKEN_BUDGET:
                    context_parts.append(content)
                    total_tokens += content_tokens
                else:
                    logger.debug(f"Skipping {file_path} - would exceed token budget")
                    break
        
        logger.info(f"Built context with ~{total_tokens} tokens from {len(context_parts)} files")
        
        return "\n".join(context_parts)