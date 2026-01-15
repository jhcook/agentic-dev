# Commands Reference

## Core Commands

### `agent new-story <title>`
Creates a new story artifact.
- **Args**: Title of the story.
- **Output**: A markdown file in `.agent/cache/stories/`.

### `agent new-runbook <story-id>`
Generates an implementation runbook for a committed story.
- **Args**: The ID of the story (e.g., `STORY-001`).

### `agent preflight`
Runs governance checks on the current codebase or a specific story.
- **Flags**:
    - `--story <id>`: Check specific story requirements.
    - `--ai`: Use AI to analyze compliance.

### `agent commit`
Commits changes with a governed message.
- **Flags**:
    - `--story <id>`: Link commit to a story.

### `agent pr`
Creates a Pull Request with the preflight summary included.
- **Flags**:
    - `--story <id>`: Link PR to a story.

## Synchronization

### `agent sync push`
Pushes local artifacts (stories, plans, runbooks) to Supabase.
- **Requires**: `SUPABASE_ACCESS_TOKEN`.

### `agent sync pull`
Pulls remote artifacts to the local cache.

### `agent sync status`
Shows the sync status of local artifacts.

## Utility

### `agent list-stories`
Lists all stories and their status.

### `agent list-runbooks`
Lists all runbooks.
