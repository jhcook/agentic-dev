# Check Domain Architecture

The `check` domain is responsible for analyzing code changes, performing static analysis, executing tests, running preflight governance blocks, evaluating impact, and synchronizing project knowledge across documentation tools.

## Extracted Packages

The core command logic `commands/check.py` has been decomposed into smaller decoupled components located in `core/check/`:

- `impact.py`: Responsible for structural and AI-driven impact analysis logic of code changes.
- `journeys.py`: Contains logic spanning user journey coverage, test execution, and mapping changed files to active journeys.
- `models.py`: Definitions of models and TypedDicts related to checks.
- `preflight.py`: Orchestrates the execution sequence for checking out the preflight rules against git diffs and code.
- `rendering.py`: Centralized text rendering logic, output formatting, Rich console styling, and reporting logic.
- `reporting.py`: Preflight json and text artifact reporting structure.
- `syncing.py`: Connectors for Oracle patterns, sync handlers referencing Notion, NotebookLM, or Local Vector Databases.
- `testing.py`: Execution of smart tests, selecting the best strategies across Python, NPM, Web, and Mobile domains.

## Structure

The CLI commands found in `agent.commands` import and compose these `core/check/` modules without owning the specific orchestration directly.

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
