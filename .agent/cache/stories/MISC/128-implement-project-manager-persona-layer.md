# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*

## Problem Statement

Project management functionalities are currently tightly coupled with core infrastructure management (originally defined in INFRA-098). This lack of separation creates a cluttered user experience for non-technical leads and prevents granular Role-Based Access Control (RBAC), leading to security risks where project leads have unnecessary access to infrastructure configurations.

## User Story

As a **Project Manager**, I want **a dedicated persona layer with scoped tools and views** so that I can **monitor project progress and allocate resources without exposure to low-level infrastructure settings.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a user authenticated with the "Project Manager" role, When they access the platform, Then they are presented with a PM-specific dashboard focusing on timelines, tasks, and budgets.
- [ ] **Scenario 2**: The interface must hide all infrastructure-specific controls (e.g., server provisioning, network configuration) from the PM view.
- [ ] **Negative Test**: System handles unauthorized access attempts to INFRA-098 endpoints by PM users by returning a 403 Forbidden error and logging the event.

## Non-Functional Requirements

- **Performance**: Persona-based UI elements must load in under 200ms after authentication.
- **Security**: Strict adherence to the Principle of Least Privilege (PoLP); project data must be logically isolated.
- **Compliance**: Ensure all PM-layer activities are captured in the audit log for SOC2 compliance.
- **Observability**: Track persona-specific engagement metrics via telemetry.

## Linked ADRs

- ADR-012: Separation of Concerns for Persona-Based Architecture

## Linked Journeys

- JRN-005: Project Manager Onboarding
- JRN-009: Resource Allocation Workflow

## Impact Analysis Summary

**Components touched:** Frontend (Persona Router), API Gateway (RBAC Middleware), Identity Provider (Roles mapping).
**Workflows affected:** User Login, Project Creation, Permission Provisioning.
**Risks identified:** Potential for permission gaps during the migration from INFRA-098; UI regression for existing admin users.

## Test Strategy

Verification will include unit testing for the new RBAC middleware, integration testing for persona-specific route guarding, and User Acceptance Testing (UAT) with the Project Management Office (PMO).

## Rollback Plan

Revert the API Gateway middleware to the previous INFRA-098 monolithic permission set and toggle off the "PM Persona" feature flag in the frontend.

## Copyright

Copyright 2026 Justin Cook