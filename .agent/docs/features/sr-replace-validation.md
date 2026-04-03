# S/R REPLACE-Side Semantic Validation (INFRA-180)

Added in INFRA-180. The `validate_sr_blocks` function in `agent/commands/utils.py` now validates the **REPLACE side** of every `[MODIFY]` block in addition to the SEARCH-match check.

## Checks Applied (`.py` files only unless noted)

| Check | Description | Config Flag | Log Event |
|-------|-------------|-------------|-----------|
| **Projected Syntax** | Applies REPLACE in memory and runs `ast.parse()` | `sr_check_syntax` | `sr_replace_syntax_fail` |
| **Import Existence** | Verifies new `from agent.X import Y` statements resolve on disk | `sr_check_imports` | `sr_replace_import_fail` |
| **Signature Stability** | Detects public function arg-list changes | `sr_check_signatures` | `sr_replace_signature_fail` |
| **Stub Regression** | Warns when REPLACE < 25% of SEARCH LOC (all file types) | `sr_stub_threshold` | `sr_replace_regression_warn` |

## Disabling Checks

All checks have config kill-switches. Set in `.agent/src/agent/core/config.py`:

```python
sr_check_syntax = False      # disable syntax projection
sr_check_imports = False     # disable import resolution
sr_check_signatures = False  # disable signature stability
sr_stub_threshold = 0.0      # disable stub regression guard
```

## Re-Anchoring Awareness

Checks run on the **current** REPLACE text even after the re-anchoring loop has corrected the SEARCH. A corrected SEARCH anchor with a hallucinated REPLACE will still be caught.

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