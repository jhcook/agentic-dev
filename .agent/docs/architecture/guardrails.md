<!--
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
-->

# Agent Execution Guardrails

Guardrails are implemented via the `ExecutionGuardrail` class which logs and monitors tool usage to prevent infinite loops and cap maximum iterations. Refer to ADR-042.

## Configuration
The following environment variables control the behavior of the execution guardrails:
- `MAX_ITERATIONS`: The maximum number of tool execution loops allowed before the agent is aborted. Default: 10
- `ENABLE_LOOP_GUARDRAILS`: true/false flag to enable detection of infinite loops (calling the exact same tool with the exact same inputs consecutively). Default: true
- `LOOP_GUARDRAIL_EXCLUDE_TOOLS`: Comma-separated list of tool names that should be ignored by the loop detection filter. Useful for tools like `list_files` where calling it repeatedly with the same directory parameter is a valid behavior for monitoring progress. Default: ""


