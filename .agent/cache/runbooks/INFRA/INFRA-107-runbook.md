# INFRA-107: Harden Runbook Generation with Targeted Codebase Introspection

## State

COMMITTED

## Goal Description

Extend `agent new-runbook` with three new context functions that inject story-specific source code reality into the AI prompt, eliminating the class of runbook errors seen in INFRA-100. This makes `agent panel` redundant for design review.

## Linked Journeys

- JRN-089: Generate Runbook with Targeted Codebase Introspection

## Panel Review Findings

### @Architect
- **Compliance**: Extends the existing `ContextLoader` pattern established in INFRA-066.
- **Design**: Three pure functions (`_load_targeted_context`, `_load_test_impact`, `_load_behavioral_contracts`) with no side effects — clean decomposition.
- **Boundary Check**: These functions live in `context.py` or `runbook.py`, not in governance. No architectural boundary violations.

### @QA
- **Coverage**: Six unit tests covering happy path, file-not-found, missing directories, and integration.
- **Strategy**: Each function is independently testable with filesystem fixtures.
- **Edge Cases**: Empty story content, story with no file references, tests directory missing.

### @Security
- **Secret Handling**: All output passes through `scrub_sensitive_data()` before prompt injection.
- **Dependency Check**: No new dependencies. Uses only `re`, `os`, `pathlib` (stdlib).

### @Product
- **User Impact**: Runbooks become directly actionable — no more rewriting aspirational code.
- **Velocity**: Eliminates the panel step from the pipeline, reducing story cycle time.

### @Observability
- **Logging**: DEBUG-level logs for context size, file count, patch target count.

### @Docs
- **Internal Docs**: Template additions are self-documenting.

### @Compliance
- **Licensing**: New functions added to existing files — no new file headers needed.

### @Backend
- **Strict Typing**: Functions return `str`, accept `str` — simple interfaces.
- **Performance**: File reads are bounded by story scope (typically 2-5 files). Sub-second impact.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Increase `AGENT_SOURCE_CONTEXT_CHAR_LIMIT` default from 8000 to 16000 for non-GH providers
- [ ] Remove `"tests"` from `exclude_dirs` in `_load_source_snippets()` (now that targeted loading handles test awareness)

## Codebase Introspection

### Target File Signatures (from source)

**`src/agent/core/context.py`** (338 LOC):

```
class ContextLoader:
    async def load_context(self, story_id: str = "", legacy_context: bool = False) -> Dict[str, Any]
    def _load_global_rules(self) -> str
    def _load_agents(self) -> dict
    def _load_role_instructions(self) -> str
    def _load_adrs(self) -> str
    def _load_source_tree(self) -> str
    def _load_source_snippets(self, budget: int = 0) -> str
```

**`src/agent/commands/runbook.py`** (433 LOC):

```
def score_story_complexity(content: str) -> ComplexityMetrics
def generate_decomposition_plan(story_id: str, story_content: str) -> str
def new_runbook(story_id, provider, skip_forecast)  # Typer command
def _load_journey_context() -> str
def _parse_split_request(content: str) -> Optional[dict]
```

**`templates/runbook-template.md`** (69 LOC):

```
Sections: State, Goal Description, Linked Journeys, Panel Review Findings,
          Targeted Refactors, Implementation Steps, Verification Plan,
          Definition of Done, Copyright
```

### Test Impact Matrix

| Test File | Patch Target | Relevance |
|-----------|-------------|-----------|
| (none — `context.py` and `runbook.py` are not currently mocked in existing tests for this feature) | — | No existing mock migration needed |

## Implementation Steps

### Component 1: Targeted Context Functions

#### [MODIFY] `src/agent/core/context.py`

Add three new methods to `ContextLoader`:

**1. `_load_targeted_context(self, story_content: str) -> str`**

- Parse file paths from story content using regex:

  ```python
  re.findall(
      r'(?:MODIFY|NEW|DELETE|refactor|decompose)\s+[`"]?'
      r'([a-zA-Z0-9_/.-]+\.py)[`"]?',
      story_content, re.IGNORECASE
  )
  ```

- For each unique path, resolve using `_resolve_file_path()` logic (try raw, relative to CWD, common prefixes like `.agent/src/`)
- If resolved: extract ALL import lines (up to 30) and ALL `class/def/async def` signatures using the existing `sig_pattern` regex from `_load_source_snippets()`
- If not resolved: emit `--- {path} --- FILE NOT FOUND (verify path!)\n`
- Return formatted string with header `TARGETED FILE SIGNATURES:\n`
- Pass result through `scrub_sensitive_data()`
- Log file count at DEBUG level

**2. `_load_test_impact(self, story_content: str) -> str`**

- Extract module path fragments from story content:

  ```python
  # Find dotted module paths and file paths, convert to dotted form
  modules = set()
  for path in re.findall(r'([a-zA-Z0-9_/.-]+\.py)', story_content):
      # core/ai/service.py -> agent.core.ai.service
      dotted = path.replace('/', '.').replace('.py', '')
      if 'agent.' not in dotted:
          dotted = 'agent.' + dotted
      modules.add(dotted)
  ```

- Walk `.agent/tests/` directory, read each `.py` file
- Find all `patch("...")` and `patch('...')` calls via regex
- If any patch string contains a module fragment, include in output
- Format: `{test_file_rel_path}:\n  - patch("{target}")\n`
- Return formatted string with header `TEST IMPACT MATRIX:\n`
- Log count of affected test files at DEBUG level

**3. `_load_behavioral_contracts(self, story_content: str) -> str`**

- Extract module names (stems) from story file paths
- Walk `.agent/tests/`, read files referencing those module names
- Extract lines matching:

  ```python
  re.findall(r'(assert\w*\s*.*?(?:default|fallback|timeout|temperature|auto_)\s*[=!<>]+\s*[^\n,)]+)', content)
  ```

- Also extract function calls with keyword defaults:

  ```python
  re.findall(r'(\w+\([^)]*(?:default|fallback|auto_)\w*\s*=\s*[^,)]+)', content)
  ```

- Format: `{test_file}: {extracted_contracts}\n`
- Return formatted string with header `BEHAVIORAL CONTRACTS:\n`

### Component 2: Prompt Integration

#### [MODIFY] `src/agent/commands/runbook.py`

**In `new_runbook()` function, after line 230 (`source_code = ctx.get("source_code", "")`):**

Add targeted context loading:

```python
# INFRA-107: Targeted introspection for story-referenced files
targeted_context = context_loader._load_targeted_context(story_content)
test_impact = context_loader._load_test_impact(story_content)
behavioral_contracts = context_loader._load_behavioral_contracts(story_content)

if targeted_context or test_impact:
    total = len(targeted_context) + len(test_impact) + len(behavioral_contracts)
    console.print(f"[dim]ℹ️  Targeted introspection: {total} chars[/dim]")
```

**In the `user_prompt` f-string (after SOURCE CODE OUTLINES block, before "Generate the runbook now."):**

Add three new sections:

```python
TARGETED FILE SIGNATURES (critical — actual signatures of files in scope):
{targeted_context if targeted_context else "(No targeted files identified in story)"}

TEST IMPACT MATRIX (tests with patch targets for these modules — MUST be addressed):
{test_impact if test_impact else "(No test impact detected)"}

BEHAVIORAL CONTRACTS (defaults and invariants — MUST be preserved):
{behavioral_contracts if behavioral_contracts else "(No behavioral contracts found)"}
```

**In the `system_prompt`, add to instruction #7:**

```
8. You MUST copy actual function signatures from TARGETED FILE SIGNATURES into the Codebase Introspection section. Do NOT paraphrase or modify signatures.
9. You MUST list all patch targets from TEST IMPACT MATRIX in the Test Impact Matrix section and specify the new patch target for each.
10. You MUST preserve all BEHAVIORAL CONTRACTS. If a default value or invariant must change, explicitly document it in the runbook step.
```

### Component 3: Template Updates

#### [MODIFY] `templates/runbook-template.md`

After `## Panel Review Findings` section (line 19), add:

```markdown
## Codebase Introspection

### Target File Signatures (from source)

(Agent: Copy actual function/class signatures from TARGETED FILE SIGNATURES context. Do NOT invent signatures.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| (Agent: Populate from TEST IMPACT MATRIX context) | | | |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| (Agent: Populate from BEHAVIORAL CONTRACTS context) | | | |
```

## Verification Plan

### Automated Tests

- [ ] `test_load_targeted_context_happy_path`: Story with `#### [MODIFY] core/ai/service.py` → returns signatures
- [ ] `test_load_targeted_context_file_not_found`: Story with nonexistent path → returns FILE NOT FOUND warning
- [ ] `test_load_targeted_context_empty_story`: Empty story content → returns header only
- [ ] `test_load_test_impact_finds_patches`: Test file with `patch("agent.core.ai.service.X")` → found
- [ ] `test_load_test_impact_no_tests_dir`: Missing tests directory → returns header only
- [ ] `test_load_behavioral_contracts_extracts_defaults`: Test with `assert auto_fallback == True` → extracted

### Manual Verification

- [ ] Run `agent new-runbook INFRA-100 --skip-forecast` and verify Codebase Introspection section contains actual `service.py` signatures
- [ ] Verify Test Impact Matrix shows `test_ai.py`, `test_ai_service.py` patch targets
- [ ] Verify no secrets or PII in generated context

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] DEBUG logs for targeted context size and test impact count

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed

## Copyright

Copyright 2026 Justin Cook
