# INFRA-017: Implement Agent Query

## State
COMMITTED

## Problem Statement
Finding specific information in a large, governed agentic codebase is difficult. Developers often have questions like "Where is the logic for X defined?" or "How do I create a new workflow?" that would require reading multiple markdown files or grep searching code. There is no central, natural-language interface to query the repository's knowledge base (Docs, ADRs, Code).

## User Story
As a developer, I want to run `env -u VIRTUAL_ENV uv run agent query "text"` to ask natural language questions about the codebase and receive an answer grounded in the repository's actual content (RAG), so that I can unblock myself without context switching or manual searching.

## Acceptance Criteria
- [ ] **Context Retrieval**: The command uses a "Smart Keyword Search" (heuristics + grep) to find relevant chunks from `docs/`, `.agent/workflows`, and `src/`. *Note: Vector database is out of scope for MVP.*
- [ ] **Security Filter**: The context builder **MUST** respect `.gitignore` rules and run the existing PII Scrubber on all chunks *before* sending them to the LLM.
- [ ] **AI Synthesis**: The retrieved chunks are passed to the LLM (Gemini/OpenAI) to generate a concise answer.
- [ ] **Citations**: The response lists the source files (e.g., "[Source: .agent/workflows/pr.md]") used to generate the answer.
- [ ] **Rate Limiting**: The system handles LLM API Rate Limits (429) gracefully with exponential backoff.
- [ ] **Conversation History** (Optional MVP): The command supports a `--chat` flag for a multi-turn session, or defaults to single-turn.
- [ ] **Offline Mode**: If `.env` is missing keys, it falls back to a basic grep/find search or fails gracefully with a clear message.

## Non-Functional Requirements
- **Latency**: Answers should be generated within 5-10 seconds.
- **Performance**: context building should use `asyncio` for parallel file reading.
- **Cost**: Context window usage should be optimized (truncate large files).
- **Accuracy**: The model should refuse to answer if the context is insufficient, rather than hallucinating.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/query.py` (new), `agent/core/ai/rag.py` (new).
Workflows affected: Developer Productivity / Support.
Risks identified: Data Exfiltration (mitigated by Security Filter AC).

## Test Strategy
- **Unit Tests**:
    - Mock the `AIService` query method to verify the CLI flows.
    - Test the `ContextBuilder` specifically for `.gitignore` adherence (create a dummy ignored file and ensure it is NOT read).
    - Test PII scrubbing integration.
- **Manual Verification**:
    - Ask questions with known answers ("How do I create a story?") and verify correctness.
    - Ask questions about non-existent features and verify it doesn't hallucinate.

## Rollback Plan
- Delete the command file.
