# Agent Console Tools

The agent console provides **14 tools** across two categories: 5 read-only (available to all agents including governance) and 9 interactive (for the console's agentic loop).

## Read-Only Tools

These tools are available to all agents for discovery and analysis.

| Tool | Description |
|------|-------------|
| `read_file(path)` | Reads a file from the repository, capped at 2000 lines. Path must be relative to repo root. |
| `search_codebase(query)` | Searches the entire codebase for a query using ripgrep. Returns up to 50 matches. For targeted searches, use `grep_search`. |
| `list_directory(path)` | Lists the contents of a directory within the repository. |
| `read_adr(adr_id)` | Reads an Architecture Decision Record by ID (e.g., '029'). |
| `read_journey(journey_id)` | Reads a User Journey by ID (e.g., '033'). |

## Interactive Tools

These tools can modify files and the system state. They are available to the main interactive agent.

| Tool | Description |
|------|-------------|
| `patch_file(path, search, replace)` | Replace exact text chunk in a file. Auto-stages the file on success. |
| `edit_file(path, content)` | Write/overwrite entire file content. Auto-stages the file on success. |
| `create_file(path, content?)` | Create a new file (errors if it already exists). Auto-stages the file on success. |
| `delete_file(path)` | Deletes a file. If the file is tracked by git, `git rm` is used to stage the deletion. |
| `run_command(command, background?)` | Execute a shell command (sandboxed to repo root). Can be run in the background. |
| `send_command_input(command_id, input_text)` | Send stdin to a running background command. |
| `check_command_status(command_id)` | Check output/status of a background command. |
| `find_files(pattern)` | Finds files matching a glob pattern within the repository. |
| `grep_search(pattern, path?)` | Search file contents using ripgrep. Searches the full repo by default. |

---

## Copyright 2026 Justin Cook
