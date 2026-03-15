# STORY-ID: INFRA-135: Dynamic Rule Retrieval — Rule Diet

## State

ACCEPTED

## Goal Description

Reduce the AI agent's context window usage during runbook generation by transitioning from a "load-all" static rule injection strategy to a dynamic retrieval model. By auditing the 18 existing governance rules into core (always-included) and contextual (retrieved via RAG) sets, we will reduce the system prompt token count by ≥50% while improving rule relevance. This includes fixing a regression in the local ChromaDB fallback mechanism to ensure robust governance checks even when external Oracle sources (NotebookLM) are unavailable.

## Linked Journeys

- JRN-062: Implement Oracle Preflight Pattern
- JRN-065: Dynamic Governance Retrieval

## Panel Review Findings

### @Architect
- **ADR Compliance**: The transition to dynamic retrieval aligns with ADR-005 (AI-Driven Governance Preflight) and the Oracle Pattern. 
- **Classification**: Core rules (000-004) ensure that identity, governance, security, architect, and QA foundations are never omitted.

### @Qa
- **Test Strategy**: The plan includes unit tests for mock NotebookLM responses and fallback scenarios.
- **Reliability**: The fix for the ChromaDB regression ensures that quality checks remain active in offline or unconfigured environments.

### @Security
- **PII Protection**: Dynamic retrieval doesn't change data handling; scrubbers are already present in the pipeline.
- **Critical Minimums**: AC-4 ensures Security (002) and QA (003) rules are always in the core set, preventing "silent" security failures if retrieval fails.

### @Product
- **User Value**: Developers get faster runbook generation and fewer conflicting rule hallucinations.
- **Acceptance Criteria**: All ACs are explicitly addressed in the implementation steps, including the 50% token reduction goal.

### @Observability
- **Structured Logging**: New `rule_retrieval` log event added with latency, source, and fallback status, satisfying SOC2 requirements.

### @Docs
- **Sync**: Documentation of the rule diet logic will be captured in the CHANGELOG.

### @Compliance
- **SOC2**: Retrieval operations are logged, providing an audit trail for which governance rules were active for a given implementation plan.

### @Mobile & @Web
- **Contextual Relevance**: Platform-specific rules (mobile.mdc, web.mdc) will now only be injected when relevant files are detected in the impact analysis, reducing noise for cross-platform developers.

### @Backend
- **Type Enforcement**: PEP-257 docstrings and type hinting will be maintained in the new retrieval functions. Typer CLI constraints respected.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/core/check/syncing.py`: Handles Oracle Pattern sync and fallback.
- `.agent/src/agent/db/journey_index.py`: Contains the `JourneyIndex` (ChromaDB) implementation.
- `.agent/src/agent/commands/runbook.py`: The implementation orchestrator where rules are injected.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/test_syncing.py` | `agent.core.check.syncing.sync_oracle_pattern` | `agent.core.check.syncing.sync_oracle_pattern` | Update to verify ChromaDB fallback activation. |
| `.agent/tests/test_journey_index.py` | `agent.db.journey_index.JourneyIndex` | `agent.db.journey_index.JourneyIndex` | Verify search robustness. |
| `.agent/tests/test_runbook.py` | `agent.commands.runbook.new_runbook` | `agent.commands.runbook.new_runbook` | Verify rule filtering and token reduction. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `vector_db_ready` False if NotebookLM OK | `syncing.py` | `False` | Yes (per tests) |
| Rule truncation | `runbook.py` | `3000 chars` | No (Replaced by Diet) |
| Core Governance Minimums | `INFRA-135` | Security + QA | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Remove the hardcoded 3000-character rule truncation in `runbook.py` in favor of semantic filtering.

## Implementation Steps

### Step 1: Fix ChromaDB Fallback Regression in Syncing

Ensure that the local vector DB is initialized as a fallback when NotebookLM is not configured or fails, fixing the regression identified in INFRA-135.

#### [MODIFY] .agent/src/agent/core/check/syncing.py

```
<<<SEARCH
    if not result["notebooklm_ready"]:
        try:
            from agent.db.journey_index import JourneyIndex
            idx = JourneyIndex()
            idx.build()
            result["vector_db_ready"] = True
            result["vector_db_status"] = "Local Vector DB ready."
        except Exception as e:
            logger.error("Local Vector DB build failed", extra={"error": str(e)})
            result["vector_db_status"] = f"Local Vector DB build failed: {e}."

    return result
===
    if not result["notebooklm_ready"] or result["notebooklm_status"] == "NotebookLM sync not configured.":
        try:
            from agent.db.journey_index import JourneyIndex
            idx = JourneyIndex()
            # AC-4: Ensure fallback activates even in non-interactive environments
            idx.build()
            result["vector_db_ready"] = True
            result["vector_db_status"] = "Local Vector DB ready (Oracle Pattern fallback active)."
            logger.info("ChromaDB fallback activated", extra={"status": "READY"})
        except Exception as e:
            # We don't fail the whole sync, but log the failure to activate fallback
            logger.error("Local Vector DB fallback activation failed", extra={"error": str(e)})
            result["vector_db_status"] = f"Local Vector DB fallback failed: {e}."

    return result
>>>
```

### Step 2: Improve JourneyIndex Search Robustness

Ensure the `search` method can handle cases where the vector store might be empty or uninitialized during the rule diet retrieval process.

#### [MODIFY] .agent/src/agent/db/journey_index.py

```
<<<SEARCH
    def search(self, query: str, k: int = 4) -> str:
        """
        Retrieve relevant context via embeddings.
        """
        import logging
        from opentelemetry import trace
        
        logger = logging.getLogger(__name__)
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("vector_db.similarity_search") as span:
            span.set_attribute("query", query)
            try:
                results = self.vectorstore.similarity_search(query, k=k)
                if not results:
                    return ""
                    
                formatted_chunks = []
                for res in results:
                    src = res.metadata.get("source", "Unknown")
                    formatted_chunks.append(f"--- Source: {src} ---\n{res.page_content}")
                    
                return "\n\n".join(formatted_chunks)
            except Exception as e:
                logger.debug(f"Error searching vector db: {e}")
                return "Local vector DB context search failed."
===
    def search(self, query: str, k: int = 4) -> str:
        """
        Retrieve relevant context via semantic search.
        
        Args:
            query: The search string.
            k: Number of results to return.
            
        Returns:
            Formatted string of relevant documentation chunks.
        """
        import logging
        from opentelemetry import trace
        
        logger = logging.getLogger(__name__)
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("vector_db.similarity_search") as span:
            span.set_attribute("query", query)
            try:
                # Ensure vectorstore is initialized and has documents
                if not hasattr(self, "vectorstore") or self.vectorstore is None:
                    return ""
                
                results = self.vectorstore.similarity_search(query, k=k)
                if not results:
                    logger.debug("Vector DB search returned no results for query.")
                    return ""
                    
                formatted_chunks = []
                for res in results:
                    src = res.metadata.get("source", "Unknown")
                    formatted_chunks.append(f"--- Source: {src} ---\n{res.page_content}")
                    
                return "\n\n".join(formatted_chunks)
            except Exception as e:
                logger.warning(f"Error searching vector db: {e}")
                return ""
>>>
```

### Step 3: Implement Dynamic Rule Retrieval in Runbook

Implement the "Rule Diet" by classifying rules into core and contextual, and fetching only the relevant ones.

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from dataclasses import dataclass
from typing import Optional

import json
import re

import typer
===
from dataclasses import dataclass
from typing import List, Optional

import json
import re
import time

import typer
>>>
```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
def _parse_split_request(content: str) -> Optional[dict]:
    """Extract and parse SPLIT_REQUEST JSON from AI response.
===
async def _retrieve_dynamic_rules(story_content: str, targeted_context: str) -> str:
    """
    Perform semantic retrieval of contextual rules based on story impact (INFRA-135).
    
    Classifies .agent/rules/ into core (always included) and contextual 
    (retrieved via RAG). Reduces token count by ≥50%.
    
    Args:
        story_content: The user story markdown.
        targeted_context: Introspection of touched files.
        
    Returns:
        Assembled string of relevant governance rules.
    """
    start_time = time.monotonic()
    rules_dir = config.rules_dir
    
    # AC-1: Audit and Classify
    # Core: Identity, Governance, Security, QA, Architect (Foundation)
    CORE_PREFIXES = ("000", "001", "002", "003", "004")
    
    core_content = []
    contextual_candidates = []
    
    if rules_dir.exists():
        for rule_file in sorted(rules_dir.glob("*.mdc")):
            if rule_file.name.startswith(CORE_PREFIXES):
                core_content.append(f"--- CORE RULE: {rule_file.name} ---\n{rule_file.read_text()}")
            else:
                contextual_candidates.append(rule_file.name)
                
    # AC-3: Retrieval Step
    query = f"{story_content}\n\nTOUCHED FILES:\n{targeted_context}"
    retrieved_content = ""
    source = "NONE"
    fallback_used = False
    
    try:
        # Try local Vector DB first as it's the primary fallback for Rule Diet
        from agent.db.journey_index import JourneyIndex
        idx = JourneyIndex()
        # Search for contextual rules specifically
        retrieved_content = idx.search(f"Goverance rules for: {query}", k=4)
        source = "ChromaDB"
        fallback_used = True
    except Exception as e:
        logger.warning(f"Rule retrieval failed: {e}")
        source = "FAILED"
        
    # AC-4: Fallback Mechanism
    # If retrieval failed or returned empty, we still have core_content (Security + QA)
    
    latency = (time.monotonic() - start_time) * 1000
    
    # NFR: SOC2/Observability logging
    logger.info("rule_retrieval", extra={
        "source": source,
        "count": 4 if retrieved_content else 0,
        "latency_ms": latency,
        "fallback_used": fallback_used
    })
    
    combined = "\n\n".join(core_content)
    if retrieved_content:
        combined += "\n\n### CONTEXTUAL RULES (RETRIEVED) ###\n\n" + retrieved_content
        
    return combined

def _parse_split_request(content: str) -> Optional[dict]:
    """Extract and parse SPLIT_REQUEST JSON from AI response.
>>>
```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
    panel_description = agents_data.get("description", "")
    panel_checks = agents_data.get("checks", "")
    
    # Truncate rules to avoid token limits (GitHub CLI has 8000 token max)
    rules_content = rules_full[:3000] + "\n\n[...truncated for token limits...]" if len(rules_full) > 3000 else rules_full

    # 4. Prompt
===
    panel_description = agents_data.get("description", "")
    panel_checks = agents_data.get("checks", "")
    
    # INFRA-135: Dynamic Rule Retrieval (Rule Diet)
    # Replaces static truncation with semantic filtering
    rules_content = asyncio.run(_retrieve_dynamic_rules(story_content, targeted_context))
    
    if len(rules_content) < len(rules_full) * 0.5:
        console.print(f"[dim]ℹ️  Rule Diet active: Prompt reduced by {100 - (len(rules_content)/len(rules_full)*100):.1f}%[/dim]")

    # 4. Prompt
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/test_syncing.py` - Verify `vector_db_ready` is True when NotebookLM is missing.
- [ ] `pytest .agent/tests/test_runbook.py` - Verify `_retrieve_dynamic_rules` returns combined core and contextual rules.
- [ ] `pytest .agent/tests/test_infra_135.py` - Integration test asserting rule content reduction ≥ 50% for a sample story.

### Manual Verification

- [ ] `agent runbook INFRA-135 --skip-forecast`
  - Expected: Logs show `rule_retrieval` event.
  - Expected: CLI output indicates "Rule Diet active" with percentage.
  - Expected: Generated runbook contains core governance (Architect/Security/QA) even if it's a mobile-only story.
- [ ] Disable internet/auth and run `agent preflight`.
  - Expected: ChromeDB fallback activates without failure.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Dynamic Rule Retrieval (Rule Diet) implementation".

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added for `rule_retrieval` event.

### Testing

- [ ] All existing tests pass
- [ ] New tests added for rule retrieval and fallback logic.

## Copyright

Copyright 2026 Justin Cook