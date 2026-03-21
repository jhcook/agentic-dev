# INFRA-164: Chunked Runbook Generation Pipeline

This decomposition breaks **INFRA-164** into 3 manageable stories, transitioning the monolithic `agent new-runbook` command into a robust multi-phase chunked pipeline.

### Decomposition Plan

1. **INFRA-165: Define Chunked Runbook Skeleton and Prompts**
2. **INFRA-166: Implement Phased Generation Orchestrator**
3. **INFRA-167: CLI Integration and Observability**

---

### INFRA-165: Define Chunked Runbook Skeleton and Prompts
**Description**: Define the JSON schema and the LLM prompts for Phase 1 (Skeleton) and Phase 2 (Block) generation for the chunked runbook pipeline.

### INFRA-166: Implement Phased Generation Orchestrator [SUB-PLAN]
**Description**: Implement the core logic in orchestrator.py to handle skeleton parsing, parallel block generation with retries, and final runbook assembly.
- INFRA-168: Implement Runbook Skeleton Parser and Assembly Engine
- INFRA-169: Implement Phased Generation Orchestrator with Concurrency and Retries

### INFRA-167: CLI Integration and Observability
**Description**: Update the agent new-runbook command with parallel execution, progress monitoring, token usage logging, and the --legacy-gen fallback flag.