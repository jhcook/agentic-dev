# STORY-ID: INFRA-097: Shared Agent Personality Preamble

## State

ACCEPTED

## Goal Description

Refactor the `agent console` system prompt generation to replace the hardcoded "clinical" persona with a configurable, collaborative "pair-programmer" personality. This will be achieved by reading a personality preamble and a repo-specific context file (e.g., `GEMINI.md`) from the configuration, ensuring consistency with the Antigravity AI assistant while maintaining existing runtime context and governance awareness.

## Linked Journeys

- JRN-057: Impact Analysis Workflow (Console prompts affect how impact is explained)
- JRN-062: Implement Oracle Preflight Pattern (Console is the primary interface for triggering preflights)

## Panel Review Findings

### @Architect
- **Review**: The layering approach (Personality -> Repo Context -> Runtime Context) is sound and follows a composition pattern that avoids monolithic prompt strings.
- **Check**: No new ADR is required as this refines an existing component's configuration strategy without changing the fundamental architecture.

### @Qa
- **Review**: The test strategy is comprehensive.
- **Check**: Ensure that the `_CACHED_SYSTEM_PROMPT` is properly invalidated or not interfering during unit tests that simulate different configuration states.

### @Security
- **Review**: No PII risk identified. The `personality_file` is read as plain text.
- **Check**: Ensure `personality_file` path resolution is anchored to the repository root to prevent arbitrary file reads via path traversal (e.g., `../../etc/passwd`).

### @Product
- **Review**: This addresses a major UX friction point where the tool feels "robotic."
- **Check**: ACs are clear. The "Collaborative Tone" is the primary value driver here.

### @Observability
- **Review**: The NFR for debug logging is critical.
- **Check**: Log structured data as requested: `logger.debug("system_prompt.personality_loaded", extra={"path": ..., "chars": ...})`.

### @Docs
- **Review**: Documentation of the new `console` keys in `agent.yaml` is necessary.
- **Check**: Ensure the `GEMINI.md` fallback/usage is documented in the README or internal docs.

### @Compliance
- **Review**: The preservation of the License Header template in the runtime context (AC-7) ensures that generated code remains compliant with project licensing rules.
- **Check**: License headers are present in all new/modified files.

### @Mobile
- **Review**: N/A. No mobile impact.

### @Web
- **Review**: N/A. No web impact.

### @Backend
- **Review**: Configuration schema in `core/config.py` must use strict typing (Pydantic) to ensure the CLI doesn't crash on invalid YAML.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract the 100+ line hardcoded prompt in `src/agent/tui/app.py` into a separate constant or a hidden fallback file to improve readability of `app.py`.
- [ ] Ensure `_CACHED_SYSTEM_PROMPT` in `tui/app.py` is initialized to `None` and handled thread-safely if applicable.

## Implementation Steps

### Infrastructure Config

#### [MODIFY] .agent/etc/agent.yaml

- Add the `console` configuration block with `personality_file` and `system_prompt`.

```yaml
console:
  personality_file: GEMINI.md
  system_prompt: |
    You are a collaborative pair-programmer embedded in this repository.
    You work alongside the developer — proactive but never surprising.

    ## Communication Style
    - Explain your reasoning when making decisions
    - Acknowledge mistakes warmly and correct course
    - Take proactive but bounded initiative
    - Ask for clarification rather than assuming
    - Format responses in markdown for readability
    - Be concise but not cold — you're a colleague, not a terminal
```

### Core Configuration

#### [MODIFY] src/agent/core/config.py

- Define `ConsoleConfig` class.
- Add `console` field to the main `Config` class.

```python
class ConsoleConfig(BaseModel):
    personality_file: Optional[str] = None
    system_prompt: Optional[str] = None

class Config(BaseSettings):
    # ... existing fields ...
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
```

### TUI Application Logic

#### [MODIFY] src/agent/tui/app.py

- Refactor `_build_system_prompt()` to implement the layering logic.
- Implement file reading for `personality_file` relative to `config.repo_root`.
- Add the debug log.
- Maintain the fallback to the existing hardcoded string if no config is provided.

```python
# Move existing hardcoded prompt to a constant
CLINICAL_PROMPT_FALLBACK = """... existing 100 lines ..."""

def _build_system_prompt(self) -> str:
    global _CACHED_SYSTEM_PROMPT
    if _CACHED_SYSTEM_PROMPT:
        return _CACHED_SYSTEM_PROMPT

    personality_layer = ""
    repo_context_layer = ""
    
    # Check if we use the new config or fallback
    has_custom_personality = bool(config.console.system_prompt or config.console.personality_file)
    
    if has_custom_personality:
        personality_layer = config.console.system_prompt or ""
        if config.console.personality_file:
            # Security: Resolve relative to repo root, validate stays within it
            safe_path = (Path(config.repo_root) / config.console.personality_file).resolve()
            if not str(safe_path).startswith(str(Path(config.repo_root).resolve())):
                logger.warning("system_prompt.path_rejected", extra={"path": str(safe_path)})
            elif safe_path.exists() and safe_path.is_file():
                repo_context_layer = safe_path.read_text()
                logger.debug("system_prompt.personality_loaded", extra={
                    "path": str(safe_path), 
                    "chars": len(repo_context_layer)
                })
    else:
        personality_layer = CLINICAL_PROMPT_FALLBACK

    # Runtime context (License, Project Layout, etc.) - existing logic
    runtime_context = self._get_runtime_context_string() 
    
    full_prompt = f"{personality_layer}\n\n{repo_context_layer}\n\n{runtime_context}"
    _CACHED_SYSTEM_PROMPT = full_prompt
    return full_prompt
```

### Documentation (@Docs panel feedback)

#### [MODIFY] README.md or .agent/docs/

- Document the new `console.personality_file` and `console.system_prompt` keys.
- Include an example configuration showing how to point to `GEMINI.md` or `.github/copilot-instructions.md`.

### Testing

#### [NEW] src/agent/core/tests/test_console_prompt.py

- Include project license header.
- Implement the 7 unit tests defined in the Test Strategy.
- Mock `config` and `Path.exists` to verify fallback and composition.
- Test path traversal rejection (e.g., `../../etc/passwd` must be rejected).

## Verification Plan

### Automated Tests
- [ ] `pytest src/agent/core/tests/test_console_prompt.py`
- [ ] `pytest src/agent/tui/app.py` (if existing tests exist)

### Manual Verification
1. Start `agent console`.
2. Verify debug log: `tail -f agent.log | grep system_prompt.personality_loaded`.
3. Ask the agent: "Who are you and what is your philosophy?".
4. **Assertion**: Response should mention "collaborative pair-programmer" or reflect the tone defined in `agent.yaml`.
5. Remove `console` keys from `agent.yaml` and restart.
6. **Assertion**: Tone should revert to the "clinical/assertive" style.

## Definition of Done

### Documentation
- [ ] `CHANGELOG.md` updated with "Added configurable agent personality via agent.yaml".
- [ ] Comments in `src/agent/core/config.py` explaining the `console` keys.

### Observability
- [ ] `system_prompt.personality_loaded` log is present in debug mode.
- [ ] Logs do not contain the content of `GEMINI.md`, only the character count.

### Testing
- [ ] Unit tests passed for all fallback and composition scenarios.
- [ ] Graceful handling of missing `GEMINI.md` file verified.

## Copyright

Copyright 2026 Justin Cook
