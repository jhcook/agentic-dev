# WEB-004: Advanced Management

## State

OPEN

## Problem Statement

Users currently have to manually edit YAML files and restart the agent to change configurations or prompts. This is slow and error-prone.

## User Story

As a User, I want to edit configuration and prompts directly in the Agent Console with validation and hot-reloading, so that I can iterate faster without managing files manually.

## Acceptance Criteria

- [ ] **Config Editor**: JSON Schema-based editor for `agent.yaml` and `voice.yaml`.
- [ ] **Prompt Studio**: UI to view and edit system prompts.
- [ ] **Hot Reload**: Backend applies changes immediately without restart where possible.
- [ ] **Activity Log**: Real-time stream of tool executions and agent thoughts.

## Linked ADRs

- ADR-009 (Agent Console Architecture)
