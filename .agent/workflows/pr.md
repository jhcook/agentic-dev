---
description: Create a Pull Request with preflight checks.
---

# PR Creation

## PURPOSE

Open a GitHub Pull Request for the current branch. Runs preflight governance checks automatically before PR creation.

## PROCESS

1. **Run** `agent pr --story <STORY-ID>` to create a PR with preflight checks.
2. **AI summary** with `agent pr --story <STORY-ID> --ai` for AI-generated PR body.
3. **Open in browser** with `agent pr --story <STORY-ID> --web`.
4. **Draft PR** with `agent pr --story <STORY-ID> --draft`.
5. **Skip preflight** with `agent pr --story <STORY-ID> --skip-preflight` (audit-logged with timestamp).

## FLAGS

| Flag | Description |
|------|-------------|
| `--story <ID>` | Story ID (auto-inferred from branch if omitted) |
| `--web` | Open PR in browser after creation |
| `--draft` | Create draft PR |
| `--ai` | Enable AI-generated PR body summary |
| `--provider <name>` | Force AI provider (gh, gemini, vertex, openai, anthropic) |
| `--skip-preflight` | Skip preflight checks (audit-logged with timestamp) |

## OUTPUT

The command:

1. Runs `agent preflight` against the target branch (unless `--skip-preflight`)
2. Auto-generates PR title as `[STORY-ID] <commit message>`
3. Generates PR body with Story Link, Changes summary, and Governance status
4. Scrubs sensitive data from the PR body
5. Invokes `gh pr create` with the generated title and body

## NOTES

- Requires `gh` CLI (GitHub CLI) to be installed and authenticated
- If preflight fails, PR creation is aborted
- `--skip-preflight` logs the skip with a timestamp for SOC2 audit trail
- See `agent pr --help` for all options
