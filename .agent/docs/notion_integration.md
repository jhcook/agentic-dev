# Notion Integration & Sync Architecture

The Agent CLI includes a powerful two-way synchronization engine designed to bridge the gap between local "offline-first" development and collaborative documentation in Notion.

## Core Philosophy

1. **Offline-First**: Developers create artifacts (Stories, Plans, ADRs) locally using the CLI. Code is the source of truth during development.
2. **Lint-Compliant**: The sync engine acts as a linter, ensuring that content pushed to Notion and pulled back to the repo strictly adheres to our Markdown standards (vertical rhythm, spacing).
3. **Transparent**: What you see in Markdown is what you get in Notion, and vice-versa. We use a custom "Transformation Engine" to handle this fidelity.

## Architecture

### 1. Global Unique IDs & Collision Protection

- **Allocation**: IDs (e.g., `INFRA-007`) are allocated based on your local repository state.
- **Safety**: When pushing, the engine checks the remote Notion database for ID collisions.
  - If an ID is taken by a *different* title, it warns you and requires manual confirmation to overwrite.
  - This allows you to work offline without fear of silent data corruption when you reconnect.

### 2. The Transformation Engine

We do not simply dump text into Notion. We treat Notion Blocks as a structured AST (Abstract Syntax Tree).

- **Markdown -> Blocks (Push)**:
  - Converts headers, lists, checkboxes, and code blocks into their native Notion equivalents.
  - **Robust Property Stripper**: Automatically detects if you've duplicated metadata (like `## Status: DRAFT` or `# Title`) in the body text and removes it to keep Notion pages clean.
- **Blocks -> Markdown (Pull)**:
  - **State Machine Formatting**: Re-renders Notion blocks into Markdown with strict spacing rules (e.g., ensuring blank lines before headers) to satisfy `markdownlint`.
  - **Normalization**: content is normalized (NFC Unicode, lowercased, stripped of non-alphanumeric chars) before diffing to avoid "false positive" changes.

### 3. Two-Way Sync & Conflict Resolution

#### `agent sync pull`

- Fetches all artifacts from Notion.
- **Smart Placement**: Automatically organizes files into subdirectories based on their ID prefix (e.g., `cache/plans/INFRA/INFRA-007.md`).
- **Cleanup**: Automatically deletes orphaned files in the root directory if they have been moved to a subdirectory.
- **Conflict**: If local content differs from remote, it performs a diff and asks: *Overwrite LOCAL file?*

#### `agent sync push`

- Scans local directories (`.agent/cache/stories`, `plans`, `adrs`).
- **Safety Check**: Verifies Title matches before updating (Collision Protection).
- **Snapshot Diff**: Compares the local file against the remote Notion blocks.
- **Conflict**: If content differs, it asks: *Overwrite REMOTE page?*

## Directory Structure

To keep the repository organized, the sync engine enforces strict hierarchy:

```
.agent/
├── cache/
│   ├── stories/
│   │   ├── INFRA/      <-- Scoped by ID Prefix
│   │   ├── BACKEND/
│   │   └── ...
│   ├── plans/
│   │   ├── INFRA/
│   │   └── ...
│   └── ...
└── adrs/               <-- Flat structure (ADRs are sequential)
```

## Troubleshooting

### "Duplicate ID Detected"

If the logs show `Duplicate ID detected: INFRA-007`, it means two different pages in Notion claim the same ID. The sync engine **skips** these to prevent data loss. You must resolve this in Notion by deleting or re-IDing one of the pages.

### "Title Mismatch"

If `agent sync push` warns about a Title Mismatch, it means your local ID points to a Notion page with a completely different title. This usually means someone else reused the ID. You should verify the remote page before forcing an overwrite.
