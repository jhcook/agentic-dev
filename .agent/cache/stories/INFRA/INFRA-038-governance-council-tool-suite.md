# Governance Council Tool Suite

## Status

OPEN

## Problem Statement

The Voice Agent currently lacks specific tools to perform the duties of the Governance Council roles (Architect, QA, Security, etc.). It hallucinates or fails when asked to "run tests" or "check compliance". To be a truly agentic partner, it needs executable interfaces for these domains.

## User Story

**As a** Developer using the Voice Agent
**I want** the agent to have specific tools for Architecture, QA, Security, and Project Management
**So that** I can ask it to "act as @QA and run tests" or "act as @Architect and list ADRs" effectively.

## Acceptance Criteria

- [ ] **Modular Tool Package**: Tools refactored into `backend.voice.tools.*`.
- [ ] **Git Tools**: `get_status`, `get_diff`, `get_log` implemented.
- [ ] **Architect Tools**: `list_adrs`, `read_adr`, `search_rules` implemented.
- [ ] **QA Tools**: `run_backend_tests`, `run_frontend_lint` implemented.
- [ ] **Security Tools**: `scan_secrets` implemented.
- [ ] **Observability Tools**: `check_agent_health`, `get_recent_logs` implemented.
- [ ] **Meta Tools**: `draft_new_tool` implemented for self-evolution.
- [ ] **Dynamic Registry**: `registry.py` implements discovery of custom tools.
- [ ] **Integration**: All tools registered in `orchestrator.py`.
- [ ] **Voice Prompt**: System prompt updated to reflect new capabilities.

## Implementation Plan

See `implementation_plan.md` for detailed module structure.
