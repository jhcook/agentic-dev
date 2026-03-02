# EXC-004: Python `ast.literal_eval` Fallback in ReAct Parser

## Status

Accepted

## Challenged By

@Security, ADR-040 (Agentic Tool-Calling Loop Architecture)

## Rule Reference

Standard practice is to parse tool-call arguments using strict `json.loads()` which accepts only double-quoted RFC 8259 JSON. Introducing `ast.literal_eval` allows parsing of Python dict literals, which widens the accepted input surface.

## Affected Files

- `.agent/src/agent/core/engine/parser.py` — `ReActJsonParser._extract_json()`

## Original Requirement

LLMs (particularly Gemini) frequently emit `tool_input` values as Python dicts with single-quoted keys/values (e.g., `{'path': 'file.py'}`).  `json.loads()` rejects these, causing the ReAct parser to fall back to `AgentFinish` — which treats the raw `Action:` block as the final answer and prevents any tools from executing. This silently broke the entire agentic loop at step 1.

## Justification

While `ast.literal_eval` evaluates Python literal expressions (strings, numbers, tuples, lists, dicts, booleans, None), it is **safe against code injection** because it does not execute arbitrary expressions, function calls, or imports. From the Python docs:

> "This can be used for safely evaluating strings containing Python values from untrusted sources without the need to parse the values oneself."

The implementation uses `json.loads()` as the **primary** parser and `ast.literal_eval` as a **fallback only** when `json.loads()` fails. This ensures:

1. **Strict JSON is preferred** — standard double-quoted JSON is parsed first.
2. **Python dicts are accepted** — single-quoted syntax from LLMs is handled.
3. **Python booleans are converted** — `True`/`False`/`None` are mapped to `true`/`false`/`null`.
4. **No arbitrary code execution** — `ast.literal_eval` is hardened against injection.

### Root Cause

The deeper root cause is `executor.py:_build_context()` which uses `str(dict)` to format `tool_input` in the ReAct history, producing single-quoted Python syntax that the LLM then learns and reproduces. The permanent fix is to use `json.dumps()` in `_build_context()` — the parser fallback provides defense-in-depth.

### Scope

This exception applies specifically to `ReActJsonParser._extract_json()` in `agent.core.engine.parser`.

## Conditions

Re-evaluate this exception if:

- Native function calling (structured JSON API responses from Gemini/OpenAI/Anthropic) is adopted, making the text-based ReAct parser unnecessary for those providers.
- A provider consistently generates malformed Python literals that `ast.literal_eval` cannot parse.
- The `_build_context()` root cause fix is deployed and LLMs stop generating single-quoted dicts.

## Consequences

- **Positive**: Restores the ReAct loop for LLMs that emit Python-style dicts, fixing a critical regression.
- **Positive**: Defense-in-depth — even after the `_build_context` fix, some LLMs may still produce single-quoted output.
- **Negative**: Slightly widens the accepted input surface (Python tuple/list literals are also accepted, though harmless).
- **Negative**: `ast.literal_eval` is marginally slower than `json.loads` on large inputs (negligible for typical tool_input sizes).

## Copyright

Copyright 2026 Justin Cook
