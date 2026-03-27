# INFRA-143: Project and Knowledge Domain Isolation

## Overview
This document records the architectural review for the consolidation of tools into `agent.tools.project` and `agent.tools.knowledge`.

## Domain Boundaries

**Project Domain**
- **Objective**: Manage the lifecycle of a code change.
- **Tools**: `match_story`, `read_story`, `read_runbook`, `list_stories`, `list_workflows`, `fix_story`, `list_capabilities`.
- **Dependencies**: Filesystem operations for `.agent/cache/stories/` and `.agent/cache/runbooks/`.

**Knowledge Domain**
- **Objective**: Provide access to institutional memory.
- **Tools**: `read_adr`, `read_journey`, `search_knowledge`.
- **Dependencies**: ChromaDB client for similarity search and filesystem operations for `.agent/adrs/` and `.agent/journeys/`.

## ADR-043 Compliance
Every tool implemented MUST use `@ToolRegistry.register()`. The docstrings must explicitly define the natural language interface for the agent to ensure high-accuracy tool selection.

## Migration Strategy
1. Implement new core modules.
2. Update `ToolRegistry` to point to core modules.
3. Verify that `Voice` and `Console` remain operational using the new core tools via regression tests.

Copyright 2026 Justin Cook
