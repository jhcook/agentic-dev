# ADR-027: Security Blocklist Pattern

## State

ACCEPTED

## Context

The Agent CLI includes a security validation layer (`agent.core.fixer`, `agent.core.governance`) that prevents AI-generated code fixes from containing dangerous operations. This layer works by:

1. **String matching**: A `suspicious_strings` list containing tokens like `"eval("`, `"exec("`, `"__import__"`, `"base64.b64decode"`, `"os.system"`, `"subprocess.run"`.
2. **AST analysis**: An `ast.NodeVisitor` that walks the parse tree and rejects calls to `eval`, `exec`, `globals`, `locals`, and `__import__`.

These strings appear **in the security-checking code itself**, not as actual invocations. The AI Governance Council has repeatedly misidentified these blocklist entries as real security vulnerabilities, producing false-positive `BLOCK` verdicts.

## Decision

**Blocklist strings and AST patterns in security-checking code are COMPLIANT and MUST NOT be flagged.**

### Rules for Governance Reviewers

1. **Presence ≠ Usage**: A string like `"eval("` inside a list, set, or comparison is a **detection pattern**, not an invocation. It is functionally equivalent to a regex or signature database.
2. **AST visitors are scanners**: Code that compares `node.func.id` against `"eval"` is **detecting** dangerous calls, not **making** them. This is a standard static-analysis pattern.
3. **Scope**: This ADR applies to all files in `.agent/src/agent/core/` that implement security validation, including but not limited to:
   - `fixer.py` — `_validate_patch_safety()`
   - `governance.py` — `scrub_sensitive_data()`

### How to Distinguish Blocklist from Usage

| Pattern | Classification | Example |
| --- | --- | --- |
| `"eval("` in a list/set literal | Blocklist entry | `suspicious = ["eval(", "exec("]` |
| `node.func.id == "eval"` | AST scanner | Detecting calls in parsed code |
| `eval(user_input)` | **Real vulnerability** | Actual invocation — BLOCK this |
| `exec(generated_code)` | **Real vulnerability** | Actual invocation — BLOCK this |

## Alternatives Considered

- **Moving blocklist to external config (YAML/JSON)**: Removes strings from Python source but adds deployment complexity. The false-positive problem is in AI interpretation, not file structure.
- **Obfuscating blocklist strings**: Using base64 or split strings to hide tokens from regex scanners. This hurts readability and maintainability.

## Consequences

- **Positive**: Eliminates a recurring class of false-positive governance blocks.
- **Positive**: Provides a clear, citable rule for the AI council to follow.
- **Negative**: Requires governance prompt to include ADR summaries (already implemented).
