# EXC-005: Autonomous Intra-Repository File Access for Agentic Tools

## Context
The introduction of Agentic capabilities (INFRA-088) grants the local AI agent the ability to read, search, and edit files within the repository using dedicated tools (`read_file`, `patch_file`, `edit_file`, `grep_search`).
Strict AI governance rules demand informed consent for accessing user data. The AI Governance Council flagged the lack of explicit user confirmation for each individual file access operation as a blocking compliance issue.

## Problem
Enforcing a mandatory, interactive human-in-the-loop approval prompt for *every single* read or write operation would fundamentally break the agentic workflow. An agent solving a complex issue might need to read dozens of files and patch several others; prompting the user for every action leads to severe prompt fatigue and renders the autonomous agent practically useless.

## Decision
We grant an explicit **Exemption (EXC)** to the per-operation consent requirement for intra-repository file access tools (`read_file`, `patch_file`, `edit_file`, `grep_search`, `find_files`, `list_directory`), under the following strict conditions:

1. **Implicit Consent by Usage:** We define the act of launching the local agent (`agent console`) as implicit consent for the agent to autonomously analyze and modify the contents of the *current repository*.
2. **Strict Sandboxing (Path Confinement):** The file tools must cryptographically enforce that all target paths remain strictly within the `repo_root`. Path traversal (`../`) or absolute paths pointing outside the repository are strictly blocked. (This is implemented in `_validate_path`).
3. **No Shell Execution Exemption:** This exemption **does NOT apply to shell execution**. The `run_command` tool must retain its explicit, per-invocation interactive user confirmation flow (as established by EXC-003).

By sandboxing the agent to the current working repository and maintaining the strict gate on arbitrary shell execution, we mitigate the risk of unintended system-wide modifications while enabling effective autonomous development workflows.

## Consequences
- The agent can fluidly analyze and modify repository files without interrupting the user.
- Compliance checks regarding data access consent are satisfied by this global exemption.
- The boundary of trust is explicitly defined as the repository root.

## Copyright

Copyright 2026 Justin Cook
