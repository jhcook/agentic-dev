# INFRA-074: Implement Oracle Preflight Pattern for All Providers

## State

COMMITTED

## Plan

### Problem Statement

I have audited the agentic-dev orchestration logic, specifically targeting the preflight sequence in `agent/commands/check.py`, the council assembly in `agent/core/governance.py`, and the multi-agent engines across various providers (including ADK).

The hallucinations during preflight are a direct result of Context Stuffing. The architecture is currently trying to solve complex governance checks by maximizing the context window rather than constraining the agent's focus.

Here are the critical vulnerabilities causing the attention fracture:

1. **The "Kitchen Sink" User Prompt**: By loading all rules, all ADRs, and all instructions simultaneously, the prompt forces the LLM to cross-reference hundreds of irrelevant tokens. The attention mechanism dilutes, causing the agent to hallucinate connections between unrelated architectural decisions.
2. **Expanded Diff Inflation (-U10)**: The git diff is generated with -U10 (10 lines of surrounding context). For a moderate PR touching 5 files, this injects hundreds of lines of unmodified code into the prompt. The agent loses the signal (what actually changed) in the noise (the surrounding file structure), leading to fabricated findings about code that was never touched.
3. **Defeating the ReAct Loop (The ADK Redundancy)**: Because the agent already has the answers dumped into its context window (ADRs and Rules injected at the start), the ReAct (Reason + Act) loop short-circuits. The agent attempts to reason over the bloated prompt instead of methodically utilizing its tools (read_file, read_adr) to fetch specific, verifiable facts.
4. **Fatal Voice Integration Hallucinations**: When voice-enabled agents (like architectural consultants) "speak" codebase violations using Google STT/TTS based on these fabricated findings, it destroys user trust. The strict citation requirement will ensure that voice agents explicitly cite the exact `.mdc` or ADR file, preventing confident audio hallucinations of non-existent architecture rules.

## Linked Journeys

- JRN-062

### User Story

> As an agentic-dev user and framework maintainer,
> I want all preflight agents, regardless of their underlying LLM provider (Anthropic, Gemini, OpenAI, Vertex), to use dynamic tool-driven retrieval ("Oracle Pattern") instead of static context stuffing,
> so that the agents do not hallucinate architectural violations, properly follow the ReAct loop, and verify rules strictly via source citations.

## Proposed Solution: The "Oracle" Preflight Pattern

To eliminate preflight hallucinations while maintaining the strict governance of the agentic-dev framework, we must pivot from static context injection to dynamic, tool-driven retrieval—mimicking the strict citation enforcement of NotebookLM.

For environments without access to NotebookLM or external endpoints, we will introduce a **Local Vector Database** (e.g., ChromaDB or LanceDB) to semantically index ADRs and `.mdc` rules, empowering agents to efficiently retrieve context offline. Furthermore, we will preserve the legacy "Context Stuffing" behavior as a fallback for users who prefer or require the old approach.

### Phase 1: Starve the Initial Prompt

Strip the user prompt down to the bare minimum. The agent should only receive the raw metadata of the task and a strict mandate to investigate.

- Remove `<adrs>`, `<rules>`, and global `<instructions>` from the initial assembly.
- Shrink the diff context back to standard `-U3`. If the agent needs to see the whole file, it must use the `read_file` tool.

### Phase 2: Enforce Role Isolation

Currently, global instructions bleed across roles. A dedicated `@Security` agent should never see the instructions for `@Frontend`.

- In all agent initialization workflows (e.g., `agent/core/adk/agents.py`, `agent/core/governance.py`), ensure the system instruction is tightly scoped:

  ```python
  system_instruction = (
      f"You are the {role.get('name', agent_name)} on the AI Governance Council.\n"
      f"You must use your tools to search the codebase and read ADRs.\n"
      f"You are strictly forbidden from evaluating {other_domains}.\n"
  )
  ```

### Phase 3: Mandate Tool-Driven Citations & Explicit Orchestration

Rewrite the prompt format in `governance.py` to force the agent to cite its tool usage. If the agent claims an architectural violation, it must prove it ran `read_adr` to verify the rule. Explicitly, the agentic-dev orchestrator will utilize Langgraph's `create_react_agent` (or a custom state graph) to bind the `read_file` and `read_adr` tools directly to the LLM.

- **Model Optimization**: Test tool-binding efficacy specifically with Google Gemini. Gemini's native tool-calling excels at returning reasoning alongside the tool call, which is crucial for populating the `FINDINGS: ... (Source: ...)` requirement accurately.
- Modify the output schema requirement:

  ```text
  Output your analysis in this EXACT format:
  VERDICT: PASS or BLOCK
  FINDINGS: 
  - [Finding] (Source: [Exact file path or ADR ID retrieved via tools])
  ```

  If a finding cannot be traced to a specific tool observation, you must discard it.

### Phase 4: NotebookLM MCP Integration & Local Vector Database Fallback

- **NotebookLM MCP Primary Route**: When the NotebookLM Enterprise API MCP server is detected in the environment, the agent routes its retrieval queries through the MCP server first for optimal enterprise document retrieval.
- **Local Vector DB Fallback (Offline Mobile Support)**: When the MCP server or external endpoints are unavailable, gracefully fall back to an embedded, zero-server vector database (like `sqlite-vec` or `LanceDB`) to index `docs/adrs/` and `.mdc` rules. These run purely in-process and can be easily bundled into a compiled binary for cross-platform, entirely offline use (e.g., compiled, protected mobile add-ons) without requiring a heavy Python server.
- **Legacy Mode**: Introduce a `--legacy-context` flag (or similar mechanism in `agent.yaml`) that completely bypasses the Oracle Pattern and reverts to the original Context Stuffing behavior.

## Acceptance Criteria

- [ ] **AC-1**: `agent/commands/check.py` diff generation context is reduced from `-U10` to `-U3` when Oracle Pattern is active.
- [ ] **AC-2**: `<adrs>`, `<rules>`, and global `<instructions>` are no longer statically injected into the initial user prompt unless the `--legacy-context` flag is provided.
- [ ] **AC-3**: Legacy mode (`--legacy-context`) perfectly preserves the original "Context Stuffing" behavior for users without the required endpoints.
- [ ] **AC-4**: Agent system instructions in `agent/core/adk/agents.py` are scoped to strictly forbid evaluating out-of-domain logic.
- [ ] **AC-5**: Preflight output schema strictly requires explicit verifiable citations for all findings (`Source: [Exact file path or ADR ID]`), dropping any finding without one.
- [ ] **AC-6**: Existing `read_file`, `search_codebase`, and `read_adr` tools remain fully accessible and correctly bound to all agents so they can retrieve what was removed from the prompt, irrespective of the active LLM provider.
- [ ] **AC-7**: A proof-of-concept Local Vector DB (e.g., ChromaDB/LanceDB) integration is provided to index and semantically search rules and ADRs completely locally.
- [ ] **AC-8**: E2E preflight test confirms that agents still check relevant rules by successfully searching or reading ADRs on their own.
- [ ] **AC-9**: The Oracle Pattern functions correctly and efficiently across all supported providers (e.g., `--provider anthropic`, `--provider vertex`, `--provider gemini`).
- [ ] **AC-10** (Notion Sync Awareness): Before the Oracle preflight begins, it must trigger a lightweight validation check against the Notion sync state (or automatically run the sync protocol) to ensure the Local Vector DB/tool context is identical to the source of truth, preventing stale local data from being retrieved.
- [ ] **AC-11** (NotebookLM Routing): When the NotebookLM Enterprise API MCP server is detected in the environment, retrieval queries must route through the MCP server first, deferring to the Local Vector DB only as a fallback.

## Non-Functional Requirements

- Performance: Must run faster than context stuffing approach.
- Security: No PII pushed to vendor LLMs without explicit prompt tracking.
- Compliance: SOC2 compliant audit trail for tool usage.

## Impact Analysis Summary

Components touched: `agent/commands/check.py`, `agent/core/governance.py`, `agent.sync.notion`
Workflows affected: Preflight checks, Governance assembly
Risks identified: Potential latency if tools are overused, but offset by caching.

## Test Strategy

- Run unit tests to verify tool bindings.
- Run integration tests to ensure preflight still works.
- Verify exit codes are correct and output contains properly cited findings.

## Rollback Plan

- Revert to `--legacy-context` if the new Oracle pattern has issues.
- Git revert the commit if fundamental breakages occur.

## Tests

- Run `agent preflight` on a test branch and verify trace/logs show tools `read_file` and `read_adr` being actively used.
- Verify `agent preflight` output accurately fails on true violations and passes on unrelated changes.
