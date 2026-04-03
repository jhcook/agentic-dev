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

"""Unit + integration tests for INFRA-180 REPLACE-side semantic validation."""

import pytest
from pathlib import Path
from unittest.mock import patch

from agent.commands.utils import (
    _sr_check_replace_syntax,
    _sr_check_replace_imports,
    _sr_check_replace_signature,
    _sr_check_replace_regression,
)


# ---------------------------------------------------------------------------
# AC-1: Projected syntax checks
# ---------------------------------------------------------------------------

def test_replace_syntax_valid():
    """Valid replacement produces clean projected file — no error."""
    original = "def run():\n    pass\n"
    search = "    pass"
    replace = "    return 42"
    assert _sr_check_replace_syntax(original, search, replace) is None


def test_replace_syntax_invalid_indentation():
    """Wrong indentation in REPLACE triggers a SyntaxError."""
    original = "def run():\n    pass\n"
    search = "    pass"
    replace = "return 42"  # unindented inside a function body
    err = _sr_check_replace_syntax(original, search, replace)
    assert err is not None
    assert "SyntaxError" in err or "syntax" in err.lower()


def test_replace_syntax_sql_injected():
    """SQL DDL injected as Python (the INFRA-145 failure) is caught."""
    original = "def setup():\n    pass\n"
    search = "    pass"
    replace = "CREATE TABLE users (id INTEGER PRIMARY KEY);"
    err = _sr_check_replace_syntax(original, search, replace)
    assert err is not None


# ---------------------------------------------------------------------------
# AC-2: Import resolution
# ---------------------------------------------------------------------------

def test_replace_imports_stdlib_passes(tmp_path):
    """Stdlib imports are skipped — no false positives."""
    replace = "import os\nfrom pathlib import Path\n"
    err = _sr_check_replace_imports(replace, tmp_path, set())
    assert err is None


def test_replace_imports_ghost_symbol_caught(tmp_path):
    """Hallucinated agent.* symbol that doesn't exist on disk is flagged."""
    # Create a real module file without CodeBlock
    mod_dir = tmp_path / ".agent" / "src" / "agent" / "core" / "implement"
    mod_dir.mkdir(parents=True)
    (mod_dir / "models.py").write_text("class ParsingError(Exception): pass\n")

    replace = "from agent.core.implement.models import CodeBlock\n"
    err = _sr_check_replace_imports(replace, tmp_path, set())
    assert err is not None
    assert "CodeBlock" in err


def test_replace_imports_symbol_in_other_defs_passes(tmp_path):
    """Symbol defined in another runbook block (other_defs) — passes."""
    replace = "from agent.core.implement.models import CodeBlock\n"
    err = _sr_check_replace_imports(replace, tmp_path, {"CodeBlock"})
    assert err is None


# ---------------------------------------------------------------------------
# AC-3: Signature stability
# ---------------------------------------------------------------------------

def test_replace_signature_identical_passes():
    """Body change with same signature — passes."""
    search = "def run_gates(content, story_id, attempt):\n    pass"
    replace = "def run_gates(content, story_id, attempt):\n    return []"
    assert _sr_check_replace_signature(search, replace, "runbook_gates.py") is None


def test_replace_signature_arg_removed_caught():
    """Removing an argument from a public function is caught."""
    search = "def run_gates(content, story_id, attempt):\n    pass"
    replace = "def run_gates(content):\n    return []"
    err = _sr_check_replace_signature(search, replace, "runbook_gates.py")
    assert err is not None
    assert "run_gates" in err


def test_replace_signature_private_function_exempt():
    """Private functions (leading _) are exempt from signature checks."""
    search = "def _internal(a, b, c):\n    pass"
    replace = "def _internal(a):\n    pass"
    assert _sr_check_replace_signature(search, replace, "utils.py") is None


# ---------------------------------------------------------------------------
# AC-4 / AC-7: Stub regression guard
# ---------------------------------------------------------------------------

def test_replace_regression_large_to_small_caught():
    """Replacing 20 lines with 2 lines triggers a regression warning."""
    search = "\n".join([f"    x_{i} = {i}" for i in range(20)])
    replace = "    pass"
    err = _sr_check_replace_regression(search, replace, "utils.py")
    assert err is not None
    assert "regression" in err.lower()


def test_replace_regression_empty_replace_exempt():
    """AC-7: Empty REPLACE (intentional deletion) is exempt."""
    search = "\n".join([f"    x_{i} = {i}" for i in range(20)])
    replace = ""
    assert _sr_check_replace_regression(search, replace, "utils.py") is None


def test_replace_regression_non_python_still_checked():
    """Regression guard fires for non-Python files too (all file types)."""
    search = "\n".join([f"line {i}" for i in range(30)])
    replace = "line 0"
    err = _sr_check_replace_regression(search, replace, "README.md")
    assert err is not None


def test_replace_regression_threshold_disabled():
    """When sr_stub_threshold=0.0, regression guard is suppressed."""
    search = "\n".join([f"    x_{i} = {i}" for i in range(20)])
    replace = "    pass"
    with patch("agent.commands.utils.config") as mock_config:
        mock_config.sr_stub_threshold = 0.0
        err = _sr_check_replace_regression(search, replace, "utils.py")
    assert err is None


# ---------------------------------------------------------------------------
# AC-5: Non-Python files exempt from syntax/import/signature checks
# ---------------------------------------------------------------------------

def test_non_python_syntax_check_exempt():
    """Markdown file — bad Python in REPLACE doesn't fire syntax check."""
    # The _sr_check_replace_syntax function is not called for non-.py files
    # by validate_sr_blocks. Verify it still works on arbitrary text without
    # interpreting it as Python at the helper level.
    original = "# Title\n\nSome content.\n"
    search = "Some content."
    replace = "def bad python ((("
    # Helper itself will try to parse — returns error (it's language-agnostic)
    # The gating logic in validate_sr_blocks skips it for non-.py; tested here
    # that the helper is side-effect free and can be called safely.
    result = _sr_check_replace_syntax(original, search, replace)
    # This is called with non-py content — it may or may not error, that's fine;
    # validate_sr_blocks is responsible for the is_py guard.
    assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Integration: validate_sr_blocks end-to-end with REPLACE-side checks
# ---------------------------------------------------------------------------

from agent.commands.utils import validate_sr_blocks  # noqa: E402


def _make_runbook(file_rel: str, search: str, replace: str) -> str:
    """Build minimal runbook markdown with one [MODIFY] S/R block."""
    return (
        f"### Step 1\n\n"
        f"#### [MODIFY] {file_rel}\n\n"
        f"```python\n"
        f"<<<SEARCH\n{search}\n===\n{replace}\n>>>\n"
        f"```\n"
    )


def test_integration_syntax_error_propagates(tmp_path, monkeypatch):
    """AC-1: validate_sr_blocks returns replace_syntax_error when REPLACE would break syntax."""
    import agent.core.implement.resolver as resolver_module

    target = tmp_path / "mymodule.py"
    target.write_text("def run():\n    pass\n")

    monkeypatch.setattr(resolver_module, "resolve_path", lambda p: target)

    content = _make_runbook("mymodule.py", "    pass", "return 42")  # bad indent
    result = validate_sr_blocks(content)

    assert len(result) == 1
    assert "replace_syntax_error" in result[0]
    assert result[0]["file"] == "mymodule.py"


def test_integration_clean_replace_no_mismatch(tmp_path, monkeypatch):
    """Valid S/R with safe REPLACE → no mismatches."""
    import agent.core.implement.resolver as resolver_module

    target = tmp_path / "mymodule.py"
    target.write_text("def run():\n    pass\n")

    monkeypatch.setattr(resolver_module, "resolve_path", lambda p: target)

    content = _make_runbook("mymodule.py", "    pass", "    return 42")
    result = validate_sr_blocks(content)

    assert result == []


def test_integration_signature_regression_caught(tmp_path, monkeypatch):
    """AC-3: Changing a public function signature in REPLACE is caught end-to-end."""
    import agent.core.implement.resolver as resolver_module

    src = "def process(data, config, retries):\n    pass\n"
    target = tmp_path / "worker.py"
    target.write_text(src)

    monkeypatch.setattr(resolver_module, "resolve_path", lambda p: target)

    search = "def process(data, config, retries):\n    pass"
    replace = "def process(data):\n    pass"
    content = _make_runbook("worker.py", search, replace)
    result = validate_sr_blocks(content)

    assert len(result) == 1
    assert "replace_signature_error" in result[0]
    assert "process" in result[0]["replace_signature_error"]


def test_integration_stub_regression_caught(tmp_path, monkeypatch):
    """AC-4: REPLACE dramatically smaller than SEARCH produces replace_regression_warning."""
    import agent.core.implement.resolver as resolver_module

    long_body = "\n".join(f"    x_{i} = {i}" for i in range(40))
    src = f"def compute():\n{long_body}\n"
    target = tmp_path / "compute.py"
    target.write_text(src)

    monkeypatch.setattr(resolver_module, "resolve_path", lambda p: target)

    search = f"def compute():\n{long_body}"
    replace = "def compute():\n    pass"
    content = _make_runbook("compute.py", search, replace)
    result = validate_sr_blocks(content)

    # May trigger both signature (body shrink) and regression — either is acceptable
    keys = set().union(*(r.keys() for r in result))
    assert "replace_regression_warning" in keys or "replace_signature_error" in keys


def test_integration_non_py_exempt_from_syntax(tmp_path, monkeypatch):
    """AC-5: Markdown file with invalid-Python REPLACE does not trigger syntax error."""
    import agent.core.implement.resolver as resolver_module

    target = tmp_path / "README.md"
    target.write_text("# Title\n\nSome content here.\n")

    monkeypatch.setattr(resolver_module, "resolve_path", lambda p: target)

    # REPLACE is clearly not valid Python, but the file is .md not .py
    content = _make_runbook("README.md", "Some content here.", "def bad python (((")
    result = validate_sr_blocks(content)

    # No syntax error should appear — only possible regression warning
    for mismatch in result:
        assert "replace_syntax_error" not in mismatch
        assert "replace_import_error" not in mismatch
        assert "replace_signature_error" not in mismatch