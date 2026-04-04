# INFRA-175: Runbook Generation Reliability Gates

## State
APPROVED

## Related Stories
INFRA-176, INFRA-177, INFRA-178, INFRA-179, INFRA-180, INFRA-181

## Summary
The `new-runbook` → `implement --apply` pipeline has a structural validation gap. Three distinct layers fail independently:

**Layer 0 — Fragile delimiter generation** (`runbook_generation.py` Phase 2): The LLM is instructed to emit bespoke `<<<SEARCH/===/>>>` delimiters interleaved with code content. These delimiters are nearly absent from the model's training corpus, so it frequently produces malformed output: missing `>>>` terminators, misplaced fence closings, and `#### [NEW]` headings leaking into prose. Each failure requires either a downstream correction gate or a manual runbook edit. INFRA-181 eliminates this by moving delimiter injection into Python — the model returns structured JSON, Python assembles the delimiters.

**Layer 1 — Missing outer gates** (`run_generation_gates`): No generation-time check for projected syntax validity of `[MODIFY]` results, no projected LOC check, no test import resolution.

**Layer 2 — Blind REPLACE-side validation** (`validate_sr_blocks`): The core S/R validation gate reads both `search` and `replace` from every block but only uses the SEARCH for matching. The REPLACE is never inspected. This means the re-anchoring loop can successfully fix a broken SEARCH while leaving a hallucinated REPLACE intact — giving a false `0 auto-corrected` confidence signal. The AI can replace a real 10-arg function with a 3-arg stub, introduce imports of non-existent types, or regress 300 lines to 15, and all gates pass.

This plan delivers seven targeted fixes across all three layers to make `new-runbook` genuinely dependable. INFRA-181 (M0) is the most impactful: once delimiters are injected by code, several downstream correction loops become unnecessary.

## Problem Origin
INFRA-145's `--apply` produced corrupted `tui/session.py` and a broken executor rename. INFRA-176's generated runbook (an attempt to fix this) demonstrated that the re-anchoring blind spot is more dangerous than originally understood — it successfully anchored hallucinated code to real functions.

## Objectives
- Close the outer gate gaps: projected syntax, projected LOC, test import resolution, API rename detection
- Close the REPLACE blind spot in `validate_sr_blocks`: add REPLACE-side checks for projected syntax, imports in implementation files, function signature stability, and stub regression detection
- Ensure the re-anchoring loop cannot produce a passing S/R gate with a semantically broken REPLACE

## Architecture

### Two Layers, Two Fix Strategies

```
new-runbook generation loop
│
├── Phase 2: Block generation [INFRA-181]  ← M0 (root cause fix)
│   ├── LLM emits JSON: {file, op, search, replace, content}
│   ├── Python validates schema (Pydantic)
│   └── Python injects: #### [MODIFY/NEW], <<<SEARCH, ===, >>>
│       → delimiter malformation rate: 0% (not LLM-generated)
│
├── run_generation_gates() [outer gates - INFRA-176, 177, 179]
│   ├── Gate 0: Projected LOC        ← INFRA-177
│   ├── Gate 1: Schema               ← existing
│   ├── Gate 2: Code/Docstring       ← existing
│   ├── Gate 2a: API rename          ← INFRA-179
│   ├── Gate 2b: Test import resolve ← INFRA-178
│   ├── Gate 3: S/R text match       ← existing (validate_sr_blocks)
│   │           └── REPLACE checks   ← INFRA-180 (extends validate_sr_blocks)
│   │               ├── Projected syntax
│   │               ├── Import existence (all .py files)
│   │               ├── Signature stability
│   │               └── Stub regression guard
│   ├── Gate 3.5: Projected syntax   ← INFRA-176 (outer fallback)
│   └── Gate 4: DoD                  ← existing
```

Gate 3.5 (INFRA-176) remains as an outer fallback. The primary projected syntax check belongs inside `validate_sr_blocks` (INFRA-180) where SEARCH and REPLACE are visible together. INFRA-181 (M0) eliminates the delimiter-malformation class of failures entirely, meaning many of the correction loops in M1–M5 become simpler or removable over time.

## Milestones
- M0: INFRA-181 — Structured JSON output for block generation; Python-injected delimiters *(root cause fix: eliminates delimiter malformation class of failures)*
- M1: INFRA-180 — REPLACE-side semantic validation in `validate_sr_blocks` *(closes the re-anchoring blind spot)*
- M2: INFRA-177 — Gate 0: Projected LOC check
- M3: INFRA-176 — Gate 3.5: Projected syntax (outer fallback, simplified given M1)
- M4: INFRA-178 — Gate 2 ext: Test import resolution
- M5: INFRA-179 — Gate 2 ext: API rename detection

**Note**: M0 (INFRA-181) can ship independently of M1–M5 since it does not change the runbook file format. Once M0 is live, the fence-rebalancer and `_fix_changelog_sr_headings` post-processors in `runbook_generation.py` can be deleted, reducing gate surface area for M1–M5.

## Risks & Mitigations
- Risk: REPLACE-side checks slow down the gate loop significantly
  - Mitigation: All checks are in-memory string operations or `ast.parse`; target <50ms total per block
- Risk: Signature check has false positives on intentional refactors
  - Mitigation: Block only if new signature has fewer params than old AND callers aren't updated in runbook
- Risk: Stub regression guard 30% threshold is too sensitive
  - Mitigation: Threshold is configurable via `config`; start at 25%

## Verification
- A runbook reproducing INFRA-145 failures must trigger correction prompts during generation
- A runbook reproducing INFRA-176 runbook failures must trigger correction prompts during generation
- `agent preflight` on each gating branch passes with zero collection errors
- `agent new-runbook INFRA-176` after M1 produces a clean runbook that correctly wires `check_projected_syntax` without hallucinating `CodeBlock`

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
