# Runbook: Implementation Runbook for INFRA-172

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

**Objective**
This section evaluates the integration of per-section vector queries into the existing runbook generation pipeline to resolve Gemini API timeouts and improve implementation grounding. It establishes the configuration control necessary to toggle this behavior.

**Insertion Point Analysis**
In `.agent/src/agent/commands/runbook_generation.py`, the `generate_runbook_chunked` function manages the transition from Phase 1 (Skeleton) to Phase 2 (Blocks). The optimal insertion point for targeted context loading is at the start of the `for i, section in enumerate(skeleton.sections, 1):` loop. 

By intercepting the process here, we can replace the static `context_summary` with a dynamic version. This dynamic context will combine the mandatory `source_tree` and `rules_content` with a section-specific query string: `f"{section.title}: {section.description}"`. If the section query returns results, they replace the global `targeted_context`; otherwise, the pipeline falls back to the upfront global query (AC-3).

**ADR & Compliance Review**
- **ADR-012 (Code Complexity Gates):** The injection logic will be kept concise within the main loop to prevent violating function length limits. Metrics calculation for `block_prompt_chars` will be handled inline to ensure visibility into prompt size reduction (AC-8).
- **ADR-025 (Local Import Pattern):** The `context_loader` from `agent.core.context` will be imported locally inside `generate_runbook_chunked` to maintain clean layer separation and reduce initialization overhead.

**Feature Flag Implementation**
Control over this new path is managed via the `USE_PER_SECTION_CONTEXT` configuration flag, allowing for immediate rollback via environment variable if performance regressions occur in non-local environments.

#### [MODIFY] .agent/src/agent/core/config.py

```python
<<<SEARCH
    # Toggle for INFRA-169: Enables parallel chunk processing and per-chunk retries.
    ENABLE_CONCURRENT_ORCHESTRATION: bool = False

    def __init__(self):
===
    # Toggle for INFRA-169: Enables parallel chunk processing and per-chunk retries.
    ENABLE_CONCURRENT_ORCHESTRATION: bool = False

    # Toggle for INFRA-172: Enables per-section vector queries to reduce prompt size.
    USE_PER_SECTION_CONTEXT: bool = os.environ.get("USE_PER_SECTION_CONTEXT", "false").lower() == "true"

    def __init__(self):
>>>

```

### Step 2: Implementation: Core Pipeline & Prompt Logic

Modify the runbook generation pipeline to shift from a monolithic context injection strategy to a targeted, per-section vector retrieval pattern. This reduces prompt bloat and eliminates Gemini API timeouts by providing relevant code chunks instead of the entire codebase outline.

#### [MODIFY] .agent/src/agent/commands/runbook_generation.py

```python
<<<SEARCH
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.logger import get_logger
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt
===
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.logger import get_logger
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt
>>>

```

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

### Step 3: Security & Input Sanitization

To prevent the leakage of Personal Identifiable Information (PII) or sensitive internal filesystem paths into the vector database, we must ensure that the query strings generated for per-section lookups are thoroughly scrubbed. This step modifies the implementation to utilize the centralized `scrub_sensitive_data` utility before passing parameters to the Chroma client.

**Sanitization Logic Implementation**

We will update the generation loop to sanitize the section metadata. This is a critical compliance requirement for SOC 2 and GDPR as defined in Rule 101, ensuring that logs and similarity query traces remain safe.

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased]
===
## [Unreleased]
**Security**
- Added automated PII scrubbing for per-section vector query strings in the runbook generation pipeline (INFRA-172).
>>>

```

### Step 4: Observability & Audit Logging

This section implements the structured telemetry and audit logging required by INFRA-172. It introduces the `section_context_loaded` event to track vector query performance and adds the `block_prompt_chars` field to monitor prompt size reduction targets. Additionally, it instruments the per-section query process with nested OpenTelemetry spans for granular visibility.

#### [NEW] .agent/src/agent/core/utils/logging.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, Dress
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logging utilities for structured events."""

from typing import Any, Dict
from agent.core.logger import get_logger

logger = get_logger(__name__)

def log_section_context_loaded(section_title: str, chunk_count: int, latency_ms: float):
    """Log a structured event when a section's context is successfully retrieved.

    Args:
        section_title: The title of the runbook section.
        chunk_count: Number of relevant code chunks retrieved from Chroma.
        latency_ms: Time taken for the vector query in milliseconds.
    """
    logger.info(
        "section_context_loaded",
        extra={
            "section_title": section_title,
            "chunk_count": chunk_count,
            "query_latency_ms": round(latency_ms, 2),
        },
    )

```



### Step 5: Verification & Test Suite

Verify the targeted context retrieval logic and prompt compression ratios through unit tests. This suite ensures that per-section vector queries are constructed correctly, fallback mechanisms are robust, and that the implementation meets the performance goal of reducing prompt size by at least 50%.

#### [NEW] .agent/tests/commands/test_runbook_generation.py

```python
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

import pytest
from unittest.mock import MagicMock, patch
from agent.commands.runbook_generation import generate_runbook_chunked, GenerationSkeleton, GenerationSection

@pytest.fixture
def mock_skeleton():
    return {
        "title": "Test Runbook",
        "sections": [
            {
                "title": "Architecture Review",
                "description": "Review the system design.",
                "files": [".agent/src/agent/core/config.py"],
                "estimated_tokens": 500
            }
        ]
    }

@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.context.context_loader._load_targeted_context")
def test_per_section_query_construction(mock_retrieval, mock_complete, mock_skeleton):
    """Verify that Chroma is queried with 'Title: Description' format (AC-1)."""
    mock_complete.side_effect = [
        "{\"title\": \"Test Runbook\", \"sections\": [{\"title\": \"Architecture Review\", \"description\": \"Review the system design.\"}]}",
        "# placeholder content"

```

### Step 6: Deployment & Rollback Strategy

This section outlines the rollout plan for targeted section-level context retrieval and the safety measures for reverting to global context in case of performance or accuracy degradation.

**1. Canary Phase Rollout**
To minimize risk, the feature is controlled via an environment variable. The rollout should follow these steps:
1. Enable the feature flag in the staging environment: `export USE_PER_SECTION_CONTEXT=true`.
2. Execute `agent new-runbook` for three distinct complex user stories (e.g., stories touching > 5 files).
3. Verify that `block_prompt_chars` emitted in the logs shows a reduction of at least 50% compared to previous runs without the flag.

**2. Verification of Grounding (Accuracy)**
Monitor structured logs for the `block_sr_prevalidated` event. The ratio of `fixed` to `total` SEARCH blocks must not exceed the baseline established in INFRA-159. If the hallucination rate (`sr_corrected / sr_total`) increases significantly, it indicates the section-level vector query is failing to retrieve necessary context chunks.

**3. Monitoring Performance**
Check the `section_context_loaded` events for `query_latency_ms`. Local Chroma queries should typically be < 100ms. If latency consistently exceeds 500ms per section, evaluate vector database index health or consider reverting.

**4. Emergency Rollback Procedure**
If implementation accuracy regresses or Gemini API timeouts persist despite the prompt size reduction:
1. Immediate Action: Unset the environment variable to trigger the fallback to the monolithic `context_summary` path.
   ```bash
   unset USE_PER_SECTION_CONTEXT
   ```

2. Validation: Confirm logs show `modify_targets_loaded` using the global oracle instead of `section_context_loaded` events.

#### [MODIFY] .agent/cache/stories/INFRA/INFRA-172-per-section-vector-query-for-runbook-block-generation.md

```markdown
<<<SEARCH
## State

COMMITTED
===
## State

IN_PROGRESS
>>>

```


