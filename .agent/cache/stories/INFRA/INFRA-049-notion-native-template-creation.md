# INFRA-049: Notion Native Template Creation

## State

COMMITTED

## Problem Statement

Currently, users are presented with blank pages when creating new items in Notion. The API does not support native "New" button templates. CLI-based "Janitor" scripts are poor UX.

## User Story

**As a** User
**I want** to see a "Master Template" row in each database
**So that** I can simply right-click and "Duplicate" it to start a new item with the correct structure immediately, without running CLI commands.

## Acceptance Criteria

- [ ] **Stories Template**: A row `! TEMPLATE: Story` exists in Stories DB with standard headers.
- [ ] **Plans Template**: A row `! TEMPLATE: Plan` exists in Plans DB with standard headers.
- [ ] **ADRs Template**: A row `! TEMPLATE: ADR` exists in ADRs DB with standard headers.
- [ ] **Bootstrap Integration**: The `notion_schema_manager.py` script automatically creates/updates these rows during bootstrap.
- [ ] **Idempotency**: The script does not create duplicate templates if one already exists.

## Technical Approach

- Extend `NotionSchemaManager` to have a `_ensure_templates()` method.
- Use `check_ssl_error` for robustness.
- Content injection via `append_block_children`.
