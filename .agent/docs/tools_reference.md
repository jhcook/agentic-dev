# Tools Reference: Web, Testing, Dependencies, and Context

This document provides a detailed reference for the tool domains introduced in INFRA-144. These tools enable the agent to interact with external documentation, execute structured test suites, manage environment dependencies, and perform safe multi-step edits with rollback capabilities.

## 1. Web Domain (`web.py`)

Tools for fetching external content and preparing it for LLM consumption.

**`fetch_url`**
Fetches the raw content of a URL and converts it to clean Markdown. This tool enforces a fixed 10-second timeout and a maximum payload size of 1MB (1048576 bytes).

- **Parameters:**
  - `url` (string, required): The target HTTP/HTTPS URL.
- **Returns:** A dictionary containing:
  - `success` (bool): True if fetch succeeded.
  - `output` (str): The Markdown-converted content.
  - `error` (str): Error message if unreachable or exceeds the 1MB `max_size` (returns safely without raising exception).

**`read_docs`**
Specialized fetcher optimized for documentation sites (currently a passthrough alias for `fetch_url`).

- **Returns:** A dictionary containing:
  - `success` (bool): True if fetch succeeded.
  - `output` (str): The Markdown-converted content.
  - `error` (str): Error message.

---

## 2. Testing Domain (`testing.py`)

Tools for running tests and parsing results into structured formats.

**`run_tests`**
Runs the test suite for the current project using the detected test runner (e.g., pytest).

- **Returns:** A dictionary containing:
  - `success` (bool): True if tests ran and passed.
  - `output` (dict): A JSON object with the following fields:
    - `passed` (int): Number of passed tests.
    - `failed` (int): Number of failed tests.
    - `errors` (int): Number of setup/teardown errors.
    - `coverage_pct` (float): Overall code coverage percentage.
    - `raw_output` (string): Complete original console output from the test runner (truncated for readability).
  - `error` (str): Error message.

**`run_single_test`**
Executes a specific test file or function.

- **Returns:** A dictionary containing:
  - `success` (bool): True if test ran and passed.
  - `output` (dict): A JSON object with the following fields:
    - `passed` (int): Number of passed tests.
    - `failed` (int): Number of failed tests.
    - `errors` (int): Number of setup/teardown errors.
    - `coverage_pct` (float): Overall code coverage percentage.
    - `raw_output` (string): Complete original console output from the test runner (truncated for readability).
  - `error` (str): Error message.

**`coverage_report`**
Generates a test suite coverage report. Currently a placeholder returns a string message.

- **Returns:** A dictionary containing:
  - `success` (bool): True if successful.
  - `output` (str): A string message.
  - `error` (str): Error message.

---

## 3. Dependency Domain (`deps.py`)

Wrappers for package management and security auditing.

**`add_dependency`**
Adds a package to the environment using `uv add`.

- **Returns:** A dictionary containing:
  - `success` (bool): True if added.
  - `output` (str): Success message.
  - `error` (str): Error message.

**`audit_dependencies`**
Performs a security audit of installed packages using `pip-audit` or `safety`.

- **Returns:** A dictionary containing:
  - `success` (bool): True if audit ran.
  - `output` (list): A list of structured objects (`List[AuditDependencyResult]`) detailing known vulnerabilities found in the current environment.
  - `error` (str): Error message.

**`list_outdated`**
Lists outdated dependencies via `uv pip list --outdated`.

- **Returns:** A dictionary containing:
  - `success` (bool): True if successful.
  - `output` (str): The output stream from pip list.
  - `error` (str): Error message.

---

## 4. Context Domain (`context.py`)

Tools for managing the state of the working tree during complex implementations.

**`checkpoint`**
Snapshots the current working tree (including untracked files) to allow for later restoration.

- **Mechanism:** Uses `git stash`.
- **Returns:** A dictionary containing:
  - `success` (bool): True if checkpointed.
  - `output` (str): Static success message ("Checkpoint created and applied to working tree.").
  - `error` (str): Error message.

**`rollback`**
Restores the working tree to the state of the last checkpoint.

- **Error Handling:** Returns a "no checkpoint" error if a rollback is requested without a prior checkpoint in the current session.
- **Returns:** A dictionary containing:
  - `success` (bool): True if rollback succeeded.
  - `output` (str): Success message.
  - `error` (str): Error message.

**`summarize_changes`**
Generates a diff of the current working tree against the git index to summarize changes.

- **Returns:** A dictionary containing:
  - `success` (bool): True if diff was generated.
  - `output` (str): Diff output.
  - `error` (str): Error message.

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
