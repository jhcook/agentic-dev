# STORY-ID: INFRA-017: Implement Agent Query

## State

ACCEPTED

## Goal Description

To create a new CLI command, `env -u VIRTUAL_ENV uv run agent query "text"`, that allows developers to ask natural language questions about the codebase. The command will use a Retrieval-Augmented Generation (RAG) pattern, finding relevant code and documentation snippets from the local repository, scrubbing them for PII, and using an LLM to synthesize an answer with citations. This will improve developer productivity by providing a fast, self-service way to find information.

## Panel Review Findings

- **@Architect**: The proposed MVP approach of using a "Smart Keyword Search" (e.g., `grep`) instead of a full vector database is a sound, pragmatic decision. It reduces initial complexity and infrastructure overhead. The component breakdown into `commands/query.py` and `core/ai/rag.py` is logical. I recommend creating a dedicated `agent/core/context_builder.py` to cleanly separate file discovery, I/O, and filtering logic from the AI synthesis logic. The design must be modular to allow replacing the keyword search with a vector index in the future. The use of `asyncio` for I/O is appropriate for performance.

- **@Security**: The primary risk is data exfiltration of sensitive information (code, credentials) to the third-party LLM. The specified controls are critical and non-negotiable.
    1. **`.gitignore` Adherence**: This is the first line of defense and must be rigorously tested. I also recommend adding support for a `.agentignore` file for more granular control over what the agent can see, independent of Git.
    2. **PII Scrubbing**: The mandatory call to the existing PII Scrubber for *all* context chunks before they are sent to the LLM is the most critical control. This process must be logged for audit purposes (e.g., "Scrubbed N chunks for query_id X").
    3. **Command Injection**: The user's query will be used to search files. Ensure that this is done using safe subprocess calls (e.g., `subprocess.run(['grep', query, file])`) and not by embedding the query into a shell command string (`shell=True`), which would open a command injection vulnerability.
    4. **Credential Management**: LLM API keys must be stored in `.agent/secrets/` (e.g., `.agent/secrets/llm_api_key`). The `.agent/secrets/` directory must be added to `.gitignore` to ensure credentials are never committed. Environment variables are NOT used for secrets.

- **@QA**: The test strategy is a good starting point. We need to expand it with more specific edge cases.
  - **Unit Tests**: Must cover the `ContextBuilder`'s file filtering logic exhaustively, including testing against a temporary directory with a dummy `.gitignore`. We need specific tests for the PII scrubber integration (using mocks), the rate limit backoff mechanism, and the graceful failure in offline mode.
  - **Integration Tests**: An end-to-end test should be created that mocks the filesystem and the LLM API. This test will verify that given a query, the correct files are read, the PII scrubber is called, and a well-formed prompt is sent to the LLM mock.
  - **Manual Verification**: We must test with queries that have known answers in the docs. We also must test adversarial queries (e.g., "ignore your instructions") and questions with no possible answer in the context to ensure the model refuses to answer rather than hallucinating. Testing should also verify that binary files and overly large files are handled gracefully (skipped or truncated).

- **@Docs**: This is a significant new feature for developers and requires clear documentation.
    1. **CLI Help**: The command must have a comprehensive `--help` message explaining its function, arguments, and options like `--chat`.
    2. **README**: The main `README.md` or a `CONTRIBUTING.md` guide must be updated with a section on how to use `env -u VIRTUAL_ENV uv run agent query`. This should include setup instructions for API keys in `.agent/secrets/llm_api_key` and provider config in `.agent/etc/query.yaml`.
    3. **Code Documentation**: All new modules (`rag.py`, `context_builder.py`) and public functions must have clear docstrings explaining their purpose, parameters, and return values.
    4. **CHANGELOG**: A new entry under a "Features" section must be added to `CHANGELOG.md`.

- **@Compliance**: The PII scrubbing requirement is the key compliance control. We must ensure there is no path for raw context to reach the LLM without passing through the scrubber. Logs related to this feature must be scrubbed of user query content and LLM response content to avoid persisting sensitive data. A unique, traceable ID should be logged for each query instead. All new third-party libraries (e.g., `tenacity`, `tiktoken`) must be checked for compatible software licenses.

- **@Observability**: To monitor cost, performance, and reliability, we need to instrument this feature.
  - **Logs**: All logs must be structured (JSON). We need to log the start/end of a query, the number of files found, the total context tokens, the completion tokens, and any errors (especially rate limit events). **CRITICAL**: Do NOT log the raw user query or the LLM response. Log a hash of the query or a unique request ID for correlation.
  - **Metrics**:
    - `agent_query_latency_seconds` (Histogram): Total time to get an answer.
    - `agent_query_total` (Counter): With labels for `status=[success|failure|rate_limited]`.
    - `agent_query_context_tokens` (Histogram): To monitor costs and prompt size.
    - `agent_query_completion_tokens` (Histogram): To monitor costs.

## Implementation Steps

### agent/config.py

#### MODIFY agent/config.py

- Add new configuration variables that leverage existing provider keys.

```python
# agent/config.py

import os
from pathlib import Path
import re

# ... existing config ...

SECRETS_DIR = Path(".agent/secrets")
ETC_DIR = Path(".agent/etc")

# Configuration for Agent Query feature
def get_llm_provider() -> str:
    """
    Reads LLM provider from .agent/etc/query.yaml or defaults based on available keys.
    
    Provider can be:
    - A named provider: "gemini", "openai", "gh"
    - A URL for self-hosted LLMs: "http://localhost:11434" (Ollama)
    """
    config_file = ETC_DIR / "query.yaml"
    if config_file.exists():
        import yaml
        with open(config_file) as f:
            cfg = yaml.safe_load(f) or {}
            return cfg.get("llm_provider", "gemini")
    # Auto-detect based on available keys
    if get_provider_api_key("gemini"):
        return "gemini"
    if get_provider_api_key("openai"):
        return "openai"
    return "gemini"  # Default

def is_url_provider(provider: str) -> bool:
    """Check if the provider is a URL (for self-hosted LLMs like Ollama)."""
    return provider.startswith("http://") or provider.startswith("https://")

def get_provider_api_key(provider: str) -> str | None:
    """
    Gets API key for a provider from env vars or .agent/secrets/.
    
    For URL-based providers (Ollama, etc.), returns None as they typically
    don't require API keys.
    
    Checks in order:
    1. Environment variable (e.g., GEMINI_API_KEY, OPENAI_API_KEY)
    2. .agent/secrets/<provider>_api_key file
    """
    # URL-based providers (Ollama, local LLMs) don't need API keys
    if is_url_provider(provider):
        return "local"  # Return truthy value to indicate "configured"
    
    # Provider-specific env var names
    env_var_map = {
        "gemini": ["GEMINI_API_KEY", "GEMINI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "gh": ["GH_TOKEN", "GITHUB_TOKEN"],
    }
    
    # Check environment variables first
    for env_var in env_var_map.get(provider, []):
        if os.getenv(env_var):
            return os.getenv(env_var)
    
    # Check .agent/secrets/ files
    secret_file = SECRETS_DIR / f"{provider}_api_key"
    if secret_file.exists():
        return secret_file.read_text().strip()
    
    return None

def is_ai_configured() -> bool:
    """Checks if at least one AI provider is configured."""
    provider = get_llm_provider()
    # URL-based providers are always "configured" (no API key needed)
    if is_url_provider(provider):
        return True
    return bool(get_provider_api_key(provider))
```

### .agent/etc/query.yaml

#### NEW .agent/etc/query.yaml

- Create optional configuration file for query feature.

```yaml
# .agent/etc/query.yaml
# Optional: If not present, uses router.yaml settings

# Maximum tokens for context
max_context_tokens: 8192
max_file_tokens: 4096
```

### .agent/etc/router.yaml

#### MODIFY .agent/etc/router.yaml

- Add Ollama and other self-hosted LLM providers to the existing router config.

```yaml
# Add to existing .agent/etc/router.yaml models section:

  # --- Ollama (Self-hosted) ---
  ollama-llama3:
    provider: "ollama"
    base_url: "http://localhost:11434"
    deployment_id: "llama3"
    tier: "local"
    context_window: 8192
    cost_per_1k_input: 0.0000
    cost_per_1k_output: 0.0000

  ollama-codellama:
    provider: "ollama"
    base_url: "http://localhost:11434"
    deployment_id: "codellama"
    tier: "local"
    context_window: 16384
    cost_per_1k_input: 0.0000
    cost_per_1k_output: 0.0000

# Update settings to include ollama in provider_priority:
settings:
  default_tier: "standard"
  provider_priority: ["gemini", "openai", "ollama", "gh"]
```

### .agent/secrets/ (Optional)

#### Optional: Provider-specific API key files

- If env vars are not set, keys can be stored in `.agent/secrets/<provider>_api_key`
- Example files: `gemini_api_key`, `openai_api_key`
- These files must be in `.gitignore`

```
# Example: .agent/secrets/gemini_api_key
# Put your actual API key here (no quotes, just the key)
AIza...
```

### agent/core/context_builder.py

#### NEW agent/core/context_builder.py

- Create a new module responsible for finding and building the context from the local filesystem.

```python
# agent/core/context_builder.py

import asyncio
import subprocess
from pathlib import Path
from typing import List, Set

# Assume pii_scrubber exists elsewhere
from ..pii import pii_scrubber

# Tokenizer for truncation - install tiktoken
import tiktoken

MAX_FILE_TOKENS = 4096
CONTEXT_TOKEN_BUDGET = 8192

class ContextBuilder:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.ignore_patterns = self._load_gitignore()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _load_gitignore(self) -> Set[str]:
        # Implementation to parse .gitignore and return a set of patterns
        # Consider using a library for robust parsing
        patterns = {".git/", "*.pyc", "__pycache__/"}
        try:
            with open(self.root_dir / ".gitignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.add(line)
        except FileNotFoundError:
            pass # No gitignore is fine
        return patterns

    def _is_ignored(self, path: Path) -> bool:
        # Simplified gitignore matching. A real implementation should handle wildcards etc.
        for pattern in self.ignore_patterns:
            if path.match(pattern):
                return True
        return False

    async def _find_relevant_files(self, query: str) -> List[Path]:
        # Use an async-compatible subprocess runner for grep
        # This is a simplified example. Keywords should be extracted from query.
        search_dirs = ["docs", "src", ".agent/workflows"]
        command = ['grep', '-rl', query] + [str(self.root_dir / d) for d in search_dirs]
        
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode > 1: # 0=found, 1=not found, >1=error
            # Handle grep error
            return []

        found_paths = [Path(p.decode()) for p in stdout.splitlines()]
        return [p for p in found_paths if not self._is_ignored(p)]

    async def _read_and_scrub_file(self, file_path: Path) -> str:
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                
                # Truncate based on tokens
                tokens = self.tokenizer.encode(content)
                if len(tokens) > MAX_FILE_TOKENS:
                    content = self.tokenizer.decode(tokens[:MAX_FILE_TOKENS])
                
                scrubbed_content = await pii_scrubber.scrub(content)
                return f"--- START {file_path} ---\n{scrubbed_content}\n--- END {file_path} ---\n"
        except (IOError, UnicodeDecodeError):
            return "" # Skip binary or unreadable files

    async def build_context(self, query: str) -> str:
        relevant_files = await self._find_relevant_files(query)
        tasks = [self._read_and_scrub_file(path) for path in relevant_files]
        
        chunks = await asyncio.gather(*tasks)
        
        # Assemble context respecting the overall token budget
        final_context = ""
        current_tokens = 0
        for chunk in chunks:
            chunk_tokens = len(self.tokenizer.encode(chunk))
            if current_tokens + chunk_tokens <= CONTEXT_TOKEN_BUDGET:
                final_context += chunk
                current_tokens += chunk_tokens
            else:
                break
        
        return final_context
```

### agent/core/ai/rag.py

#### NEW agent/core/ai/rag.py

- Create a service to handle the LLM interaction, including prompt construction and retry logic.

```python
# agent/core/ai/rag.py

# Install tenacity: pip install tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import is_ai_configured
from .llm_service import AIService, RateLimitError # Assumes an existing AIService

class RAGService:
    def __init__(self, ai_service: AIService):
        if not is_ai_configured():
            raise ValueError("AI Service is not configured. Add your API key to .agent/secrets/llm_api_key")
        self.ai_service = ai_service

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError)
    )
    async def answer_query(self, query: str, context: str) -> str:
        if not context:
            return "I couldn't find any relevant information in the repository to answer your question. Please try rephrasing."

        system_prompt = """
        You are a helpful AI assistant for software developers.
        Answer the user's question based *only* on the provided context from the codebase.
        The context consists of multiple file snippets, each marked with `--- START filepath ---` and `--- END filepath ---`.
        When you use information from a file, you MUST cite it at the end of your answer like this: [Source: filepath].
        If the context does not contain the answer, state that you cannot answer the question with the given information. Do not make things up.
        """
        
        user_prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{query}"
        
        response = await self.ai_service.query(system_prompt, user_prompt)
        return response
```

### agent/commands/query.py

#### NEW agent/commands/query.py

- Create the `click` command that orchestrates the workflow.

```python
# agent/commands/query.py

import click
import asyncio
from ..config import is_ai_configured
from ..core.context_builder import ContextBuilder
from ..core.ai.rag import RAGService
from ..core.ai.llm_service import get_ai_service # Factory to get OpenAI/Gemini service

@click.command()
@click.argument('text', required=True)
@click.option('--chat', is_flag=True, help="Enable multi-turn conversation mode.")
def query(text: str, chat: bool):
    """
    Asks a natural language question about the codebase.
    """
    if not is_ai_configured():
        click.echo("AI features are not configured. Please set LLM_API_KEY in your .agent/secrets/llm_api_key file.")
        click.echo("Falling back to simple grep search:")
        # Implement simple grep fallback here
        subprocess.run(['grep', '-r', text, 'docs', 'src', '.agent'])
        return

    # Placeholder for chat history management
    if chat:
        click.echo("Chat mode is not yet implemented in this MVP.")
        return

    asyncio.run(run_query(text))

async def run_query(text: str):
    click.echo("🔍 Finding relevant context...")
    
    # Assuming the command runs from the repo root
    context_builder = ContextBuilder(root_dir=Path("."))
    context = await context_builder.build_context(text)
    
    if not context.strip():
        click.echo("Could not find any relevant files for your query.")
        return

    click.echo("🧠 Synthesizing answer with AI...")
    
    try:
        ai_service = get_ai_service()
        rag_service = RAGService(ai_service)
        answer = await rag_service.answer_query(text, context)
        
        click.echo("\n✅ Answer:\n")
        click.echo(answer)
    except Exception as e:
        # Log the full error for observability
        click.echo(f"An error occurred: {e}", err=True)
```

## Verification Plan

### Automated Tests

- [ ] **`test_context_builder.py`**:
  - [ ] `test_gitignore_is_respected`: Create a temp directory with `test.txt` and `.gitignore` ignoring it; assert `_find_relevant_files` does not return `test.txt`.
  - [ ] `test_binary_files_are_skipped`: Write a binary file and assert `_read_and_scrub_file` returns an empty string or handles the error.
  - [ ] `test_large_file_is_truncated`: Create a file with 10k tokens and verify the output of `_read_and_scrub_file` is truncated to `MAX_FILE_TOKENS`.
- [ ] **`test_rag_service.py`**:
  - [ ] `test_retry_on_rate_limit`: Mock `AIService` to raise `RateLimitError` once, then succeed. Verify the `answer_query` method succeeds after two calls to the mock.
  - [ ] `test_no_context_response`: Call `answer_query` with an empty context string and verify the predefined "I couldn't find anything" response is returned.
- [ ] **`test_query_command.py`**:
  - [ ] `test_offline_mode_fallback`: Unset `LLM_API_KEY` env var, run the command, and assert the offline message and `grep` fallback are triggered.
  - [ ] `test_pii_scrubber_integration`: Use `unittest.mock.patch` to spy on the PII scrubber function and assert it is called when context is built.

### Manual Verification

- [ ] **Setup**: Configure a valid `LLM_API_KEY` in a local `.agent/secrets` file if it doesn't already exist.
- [ ] **Known Question**: Run `env -u VIRTUAL_ENV uv run agent query "how do I create a new workflow?"`. Verify the answer is coherent, accurate, and includes citations like `[Source: .agent/workflows/pr.md]`.
- [ ] **Code Question**: Run `env -u VIRTUAL_ENV uv run agent query "where is the RAGService defined?"`. Verify it correctly cites `agent/core/ai/rag.py`.
- [ ] **Offline Mode**: Remove the `.agent/secrets/llm_api_key` file. Run the command again and verify it prints the graceful failure message and shows grep results.
- [ ] **Hallucination Test**: Run `env -u VIRTUAL_ENV uv run agent query "what is the launch date for the Mars colony project?"`. Verify the model responds that it cannot answer based on the provided context.
- [ ] **`.gitignore` Test**: Create a file named `secrets.log` containing the word "workflow". Add `secrets.log` to `.gitignore`. Run `env -u VIRTUAL_ENV uv run agent query "workflow"`. Verify the answer does not cite `secrets.log`.

## Definition of Done

### Documentation

- [ ] `CHANGELOG.md` updated with an entry for the new `env -u VIRTUAL_ENV uv run agent query` feature.
- [ ] `README.md` (or contributing guide) updated to explain how to set up and use the `env -u VIRTUAL_ENV uv run agent query` command.
- [ ] CLI command includes a useful `--help` message.

### Observability

- [ ] Logs are structured (JSON) and contain a unique `query_id` for correlation.
- [ ] Logs are free of PII: user query text and LLM responses are NOT logged.
- [ ] Metrics for latency (`agent_query_latency_seconds`), token counts (`agent_query_context_tokens`, `agent_query_completion_tokens`), and invocation count (`agent_query_total`) are added.

### Testing

- [ ] All new unit tests pass with >90% code coverage for the new modules.
- [ ] Manual verification plan executed and all steps passed.
- [ ] Integration tests (mocking external services) pass.
