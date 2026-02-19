# INFRA-066: Add Source Code Context to Runbook Generation

## State

COMMITTED

## Goal Description

Enhance `context_loader.load_context()` to include source code context (file tree + targeted snippets) so that `agent new-runbook` produces runbooks with accurate file paths, correct SDK usage, and implementation steps that follow existing codebase patterns.

## Linked Journeys

- (none yet)

## Panel Review Findings

**@Architect**: Changes are confined to the Core layer (`context.py`) and the Commands layer (`runbook.py`). No upward dependencies introduced. The `ContextLoader` class already follows the correct pattern — new methods will be private instance methods consistent with `_load_global_rules()`, `_load_agents()`, etc. No new ADR needed; ADR-025 (lazy init) is not violated since `ContextLoader` is eagerly instantiated at module level as `context_loader = ContextLoader()`. Verdict: **PASS**.

**@QA**: Four unit tests covering tree generation, snippet extraction, context dict keys, and truncation logic. Integration test via `agent new-runbook` on a committed story. Tests should use `tmp_path` fixtures to create mock directory structures. Coverage target: 100% of new methods. Verdict: **PASS**.

**@Security**: Source content passes through `scrub_sensitive_data()` before prompt inclusion (compliance with `global-compliance-requirements.mdc` §1.1: no secrets in logs/prompts). The `.agent/src/` directory is developer tooling, not user data — PII risk is minimal but the scrub is still applied. `__pycache__` and `.pyc` files are excluded from tree output. Verdict: **PASS**.

**@Product**: Acceptance criteria are clear and testable. The feature is invisible to the end user except through improved output quality — no UX changes needed. Verdict: **PASS**.

**@Observability**: Source context size logged at DEBUG level via existing `logging.getLogger(__name__)` pattern. No new metrics required — this is a developer tool. Verdict: **PASS**.

**@Docs**: `CHANGELOG.md` update required. No README updates needed as this is an internal improvement. Verdict: **PASS**.

**@Compliance**: License headers required on any new test files. No PII handling. No data storage changes. Verdict: **PASS**.

**@Mobile**: Not applicable. Verdict: **PASS**.

**@Web**: Not applicable. Verdict: **PASS**.

**@Backend**: Type annotations required on all new methods. Existing patterns in `context.py` use `-> str` and `-> dict` return types. Verdict: **PASS**.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Exclude `__pycache__` directories from tree output.
- [ ] Move `import re` from inside `new_runbook()` to top-level imports in `runbook.py` (line 53).

## Implementation Steps

### Context Loader

#### [MODIFY] [context.py](file:///.agent/src/agent/core/context.py)

**Step 1: Add `_load_source_tree()` method** (after `_load_adrs()`, line 164)

Add a new private method that generates a tree representation of the source directory:

```python
def _load_source_tree(self) -> str:
    """Loads a file tree of the source directory for codebase context.

    Excludes __pycache__, .pyc files, and other non-essential items.
    Returns an indented tree string or empty string if src/ doesn't exist.
    """
    import os

    src_dir = config.agent_dir / "src"
    if not src_dir.exists() or not src_dir.is_dir():
        return ""

    exclude_dirs = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
    exclude_exts = {".pyc", ".pyo"}

    tree = "SOURCE FILE TREE:\n"
    for dirpath, dirnames, filenames in os.walk(src_dir):
        # Filter excluded directories in-place (os.walk respects this)
        dirnames[:] = sorted(
            d for d in dirnames if d not in exclude_dirs
        )
        rel = os.path.relpath(dirpath, src_dir)
        level = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * level
        dirname = os.path.basename(dirpath)
        tree += f"{indent}{dirname}/\n"
        sub_indent = "  " * (level + 1)
        for fname in sorted(filenames):
            if not any(fname.endswith(ext) for ext in exclude_exts):
                tree += f"{sub_indent}{fname}\n"

    return scrub_sensitive_data(tree)
```

**Step 2: Add `_load_source_snippets()` method** (after `_load_source_tree()`)

Add a method that extracts file outlines (imports, class/function signatures) from Python source files, staying within a character budget:

```python
def _load_source_snippets(self, budget: int = 8000) -> str:
    """Loads compact source outlines (imports + signatures) from Python files.

    Walks all .py files under src/, extracts import lines and
    class/def signatures (not bodies), and concatenates them until
    the character budget is exhausted.

    Args:
        budget: Maximum character count for combined snippets.

    Returns:
        Formatted string of source outlines, or empty string if unavailable.
    """
    import re as _re

    src_dir = config.agent_dir / "src"
    if not src_dir.exists():
        return ""

    exclude_dirs = {"__pycache__", ".pytest_cache", "tests"}
    sig_pattern = _re.compile(
        r"^((?:class|def|async\s+def)\s+\S+.*?):\s*$", _re.MULTILINE
    )

    snippets = "SOURCE CODE OUTLINES:\n"
    remaining = budget - len(snippets)

    for py_file in sorted(src_dir.rglob("*.py")):
        # Skip excluded directories
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        # Skip __init__.py with only docstrings/license
        if py_file.name == "__init__.py" and py_file.stat().st_size < 200:
            continue

        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        rel_path = py_file.relative_to(config.agent_dir)
        lines = []

        # Imports (first 20 import lines max)
        import_lines = [
            l for l in content.splitlines()
            if l.startswith(("import ", "from "))
        ][:20]
        if import_lines:
            lines.extend(import_lines)

        # Class/function signatures
        for m in sig_pattern.finditer(content):
            lines.append(m.group(1))

        if not lines:
            continue

        block = f"\n--- {rel_path} ---\n" + "\n".join(lines) + "\n"

        if len(block) > remaining:
            truncated = block[: remaining - 20] + "\n[...truncated...]\n"
            snippets += truncated
            break
        snippets += block
        remaining -= len(block)

    return scrub_sensitive_data(snippets)
```

**Step 3: Update `load_context()` return dict** (line 28-38)

Add the two new keys to the returned dictionary and add a logging import:

```diff
+import logging
 import yaml

 from agent.core.config import config
 from agent.core.utils import scrub_sensitive_data

+logger = logging.getLogger(__name__)
+

 class ContextLoader:
     def __init__(self):
         self.rules_dir = config.rules_dir
         self.agents_path = config.etc_dir / "agents.yaml"
         self.instructions_dir = config.instructions_dir
         self.adrs_dir = config.agent_dir / "adrs"

     def load_context(self) -> dict:
         """
-        Loads the full context: Global Rules, Agents, Agent Instructions, and ADRs.
+        Loads the full context: Global Rules, Agents, Agent Instructions, ADRs, and Source Code.
         Returns a dictionary with formatted strings ready for LLM consumption.
         """
+        source_tree = self._load_source_tree()
+        source_code = self._load_source_snippets()
+        logger.debug("Source context: tree=%d chars, snippets=%d chars",
+                      len(source_tree), len(source_code))
         return {
             "rules": self._load_global_rules(),
             "agents": self._load_agents(),
             "instructions": self._load_role_instructions(),
-            "adrs": self._load_adrs()
+            "adrs": self._load_adrs(),
+            "source_tree": source_tree,
+            "source_code": source_code,
         }
```

---

### Runbook Command

#### [MODIFY] [runbook.py](file:///.agent/src/agent/commands/runbook.py)

**Step 4: Wire source context into the prompt** (lines 77-146)

After `ctx = context_loader.load_context()` (line 77), extract the new keys and add them to the user prompt:

```diff
     ctx = context_loader.load_context()
     rules_full = ctx.get("rules", "")
     agents_data = ctx.get("agents", {})
     instructions_content = ctx.get("instructions", "")
     adrs_content = ctx.get("adrs", "")
+    source_tree = ctx.get("source_tree", "")
+    source_code = ctx.get("source_code", "")
```

Then add to the system prompt instructions (inside the `INSTRUCTIONS:` block, after item 6):

```diff
 6. You MUST follow the DETAILED ROLE INSTRUCTIONS for each role.
+7. You MUST use the SOURCE CODE CONTEXT to derive accurate file paths, existing patterns, and SDK usage. Do NOT invent file paths or SDK calls — use only what appears in the source tree and code outlines.
+
+INPUTS:
+1. User Story (Requirements)
+2. Governance Rules (Compliance constraints)
+3. Role Instructions (Per-role detailed guidance)
+4. ADRs (Codified architectural decisions)
+5. Source File Tree (Repository structure)
+6. Source Code Outlines (Imports, class/function signatures)
```

And add to the user prompt (before `Generate the runbook now.`):

```diff
 EXISTING USER JOURNEYS:
 {_load_journey_context()}

+SOURCE FILE TREE:
+{source_tree}
+
+SOURCE CODE OUTLINES:
+{source_code}
+
 Generate the runbook now.
```

---

### Tests

#### [NEW] [test_source_context.py](file:///.agent/src/agent/core/tests/test_source_context.py)

**Step 5: Add unit tests**

```python
# Copyright 2026 Justin Cook
# ... (license header)

"""Tests for source code context loading in ContextLoader."""

import pytest
from unittest.mock import patch
from pathlib import Path

from agent.core.context import ContextLoader


@pytest.fixture
def mock_src_tree(tmp_path):
    """Create a mock source directory structure."""
    src = tmp_path / "src" / "agent"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "config.py").write_text(
        "import yaml\nfrom pathlib import Path\n\n"
        "class Config:\n    def __init__(self):\n        pass\n"
    )
    (core / "ai").mkdir()
    (core / "ai" / "service.py").write_text(
        "from google import genai\nimport os\n\n"
        "class AIService:\n    def complete(self, system, user):\n        pass\n"
        "    def reload(self):\n        pass\n"
    )
    # Add a __pycache__ that should be excluded
    cache = core / "__pycache__"
    cache.mkdir()
    (cache / "config.cpython-312.pyc").write_text("bytecode")
    return tmp_path


class TestLoadSourceTree:
    def test_returns_tree_structure(self, mock_src_tree):
        loader = ContextLoader()
        with patch.object(loader, '_ContextLoader__get_agent_dir',
                          return_value=mock_src_tree, create=True):
            # Patch config.agent_dir
            from agent.core import config as cfg
            original = cfg.config.agent_dir
            cfg.config.agent_dir = mock_src_tree
            try:
                tree = loader._load_source_tree()
                assert "config.py" in tree
                assert "service.py" in tree
                assert "__pycache__" not in tree
                assert ".pyc" not in tree
            finally:
                cfg.config.agent_dir = original

    def test_returns_empty_when_no_src(self, tmp_path):
        from agent.core import config as cfg
        original = cfg.config.agent_dir
        cfg.config.agent_dir = tmp_path  # No src/ dir
        try:
            loader = ContextLoader()
            assert loader._load_source_tree() == ""
        finally:
            cfg.config.agent_dir = original


class TestLoadSourceSnippets:
    def test_extracts_signatures(self, mock_src_tree):
        from agent.core import config as cfg
        original = cfg.config.agent_dir
        cfg.config.agent_dir = mock_src_tree
        try:
            loader = ContextLoader()
            snippets = loader._load_source_snippets()
            assert "class Config" in snippets
            assert "class AIService" in snippets
            assert "def complete" in snippets
            assert "from google import genai" in snippets
        finally:
            cfg.config.agent_dir = original

    def test_respects_budget(self, mock_src_tree):
        from agent.core import config as cfg
        original = cfg.config.agent_dir
        cfg.config.agent_dir = mock_src_tree
        try:
            loader = ContextLoader()
            snippets = loader._load_source_snippets(budget=100)
            assert len(snippets) <= 120  # budget + small header overhead
            assert "[...truncated...]" in snippets
        finally:
            cfg.config.agent_dir = original


class TestLoadContextIncludesSource:
    def test_context_has_source_keys(self, mock_src_tree):
        from agent.core import config as cfg
        original = cfg.config.agent_dir
        cfg.config.agent_dir = mock_src_tree
        try:
            loader = ContextLoader()
            ctx = loader.load_context()
            assert "source_tree" in ctx
            assert "source_code" in ctx
        finally:
            cfg.config.agent_dir = original
```

---

### Documentation

#### [MODIFY] [CHANGELOG.md](file:///CHANGELOG.md)

**Step 6: Add changelog entry**

```markdown
### Added
- Source code context (file tree + code outlines) now included in `agent new-runbook` prompts for codebase-accurate implementation steps (INFRA-066).
```

## Verification Plan

### Automated Tests

- [ ] Test 1: `_load_source_tree()` returns tree with `config.py`, `service.py`; excludes `__pycache__/` and `.pyc`
- [ ] Test 2: `_load_source_snippets()` extracts `class Config`, `def complete`, `from google import genai`
- [ ] Test 3: `_load_source_snippets(budget=100)` truncates with `[...truncated...]`
- [ ] Test 4: `load_context()` returns dict with `source_tree` and `source_code` keys
- [ ] Test 5: `make test` passes with no regressions

### Manual Verification

- [ ] Step 1: Run `agent new-runbook` on a committed story and verify file paths reference actual repo paths (e.g., `.agent/src/agent/core/context.py` not `src/context.py`)
- [ ] Step 2: Verify runbook generation still succeeds when `src/` directory is deleted (graceful degradation)

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable) — N/A, internal improvement
- [ ] API Documentation updated (if applicable) — N/A

### Observability

- [ ] Logs are structured and free of PII
- [ ] Source context size logged at DEBUG level

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed
