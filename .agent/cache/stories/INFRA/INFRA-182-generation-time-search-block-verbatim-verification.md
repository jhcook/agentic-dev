# INFRA-182: Generation-Time SEARCH Block Verbatim Verification

## State

DRAFT

## Problem Statement

Every `agent new-runbook` run produces `[MODIFY]` blocks whose `<<<SEARCH` text is approximated
by the LLM rather than copied verbatim from disk. The fuzzy+AI correction at apply-time catches
some mismatches but not all — and when it fails the runbook requires manual intervention before
`agent implement --apply` can proceed. This has caused friction on every INFRA-17x story to date.

The fix belongs at **generation time**, not apply-time: immediately after Phase 2 assembly,
before the runbook is written to disk, sweep every `<<<SEARCH` block, read the actual target
file, find the nearest verbatim region using the existing fuzzy matcher, and replace the
LLM-approximated text with the real file content. If no region is within the similarity
threshold, surface a hard error so the human reviewer knows which block needs attention —
rather than silently saving a broken runbook.

## User Story

As a developer running `agent new-runbook`, I want every `<<<SEARCH` block in the generated
runbook to contain verbatim text from the target file on disk, so that `agent implement --apply`
succeeds on the first attempt without S/R validation failures.

## Acceptance Criteria

- [ ] **AC-1**: After Phase 2 generation, a post-process step reads every `<<<SEARCH` block from
  the assembled runbook content, opens the target file, and replaces the SEARCH text with the
  nearest verbatim match (similarity ≥ 0.7 threshold, same as the existing apply-time fuzzy
  matcher).
- [ ] **AC-2**: If no match is found above the threshold, the block is annotated with
  `# SEARCH_UNRESOLVED` and a warning is emitted — the runbook is still saved but the
  human reviewer is clearly flagged.
- [ ] **AC-3**: Files listed in `<<<SEARCH` blocks that do not exist on disk (i.e., `[NEW]`
  targets being created by the runbook) are skipped without error.
- [ ] **AC-4**: The verification step emits a structured log event
  `sr_search_verified` with `file`, `similarity`, `was_corrected` attributes per block
  (ADR-046).
- [ ] **AC-5**: Running `agent new-runbook INFRA-179` after this change produces zero S/R
  validation failures at the end of generation (the `❌ N S/R block(s) still failed` line
  disappears).

## Non-Functional Requirements

- Performance: Fuzzy match is bounded by file read + `difflib.SequenceMatcher`; target <100ms
  per block.
- Accuracy: Use the same `_fuzzy_find_block` logic already in
  `agent/commands/utils.py` — do not duplicate.
- Safety: Never modify `[NEW]` file content blocks; only touch `<<<SEARCH` regions in
  `[MODIFY]` blocks.

## Linked ADRs

- ADR-046 (Observability)

## Linked Journeys

- JRN-023

## Impact Analysis Summary

Components touched: `runbook_generation.py` (new `_verify_search_blocks` post-process step
between Phase 2 and file write), `agent/commands/utils.py` (expose/reuse `_fuzzy_find_block`).
Workflows affected: `agent new-runbook` only.
Risks identified: False positives if two regions have similar similarity scores — mitigated by
taking the highest-scoring match (same as existing fuzzy matcher behaviour).

## Test Strategy

- Unit — `_verify_search_blocks`: SEARCH text with 90% match → replaced with verbatim content
- Unit — `_verify_search_blocks`: SEARCH text with 50% match → annotated with SEARCH_UNRESOLVED
- Unit — `_verify_search_blocks`: target file does not exist → block skipped  
- Integration — `agent new-runbook` on a test story → zero `❌ S/R block(s) still failed` lines

## Rollback Plan

Remove the `_verify_search_blocks` call from `runbook_generation.py`. Purely additive; the
apply-time fuzzy matcher continues to function as before.

## Copyright

Copyright 2026 Justin Cook

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
