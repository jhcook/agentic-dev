# EXC-002: Security False Positives in Agent CLI Internal Code

## Status

Accepted

## Challenged By

@Security (CISO)

## Rule Reference

General security review — CISO repeatedly flags internal CLI code paths as vulnerable without validating the actual data flow.

## Affected Files

- `.agent/src/agent/commands/check.py` — subprocess calls, interactive repair loop
- `.agent/src/agent/core/ai/service.py` — provider initialization, error handlers
- `.agent/src/agent/core/fixer.py` — patch validation, blocklist scanning
- `.agent/src/agent/core/governance.py` — AI prompt construction, data scrubbing

## Original Findings

> 1. `check.py:463` — "validate `chosen_opt` before subprocess execution to prevent command injection"
> 2. `service.py:175` — "scrub credentials from `auth_check.stdout` before logging"

## Justification

Both findings are **false positives** caused by the AI misreading code context:

### Finding 1: `chosen_opt` and subprocess are unrelated code paths

`chosen_opt` is used in the **interactive repair loop** (lines 92–134) where it selects an AI-generated patch option. It is **never passed to `subprocess.run()`**. The subprocess call at line 451 uses `task['cmd']`, which comes from a hardcoded internal task list — not user input.

Furthermore, `chosen_opt` content is validated by `InteractiveFixer._validate_patch_safety()` which performs:

- String-based blocklist scanning (`eval(`, `exec(`, `os.system`, etc.)
- AST analysis (`ast.NodeVisitor`) blocking dangerous calls
- Import validation against an allowlist

### Finding 2: Line 175 is an `ImportError` handler

`service.py:175` catches `ImportError` when the `anthropic` package is not installed. It prints a helpful installation message. No credentials, API keys, or `auth_check.stdout` content appears at this line. The CISO conflated this with the `_check_gh_cli()` method (line 188+), which **already scrubs output** via `capture_output=True` and does not log stdout.

### Scope

This exception applies to all files under `.agent/src/` where:

- Subprocess calls use **hardcoded commands** (not user-supplied input)
- Error handlers print **static messages** (not dynamic secrets)
- Security blocklist code contains **detection patterns** (covered separately by ADR-027)

## Conditions

Re-evaluate this exception if:

- Any subprocess call in `.agent/src/` begins accepting user-supplied command strings
- Error handlers begin including dynamic content from API responses
- The CLI is exposed as a network-accessible service (see ADR-028)

## Consequences

- **Positive**: Eliminates the most persistent class of CISO false positives — misidentified data flows.
- **Positive**: Documents the actual security controls that exist (blocklist, AST validation, scrubbing).
- **Negative**: If a real subprocess injection vulnerability is introduced, developers must ensure this EXC does not suppress valid findings.
