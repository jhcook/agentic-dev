# Journey YAML Schema Reference

Complete field reference for user journey YAML files. For the lifecycle and workflow, see [user_journeys.md](user_journeys.md).

## Required Fields

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique identifier, `JRN-XXX` format |
| `title` | string | Human-readable summary |
| `actor` | string | Primary user persona |
| `description` | string | What this journey achieves |
| `steps` | list | Ordered sequence of user/system interactions |

## Optional Fields (Safe Defaults)

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `schema_version` | int | `1` | Schema version for forward compatibility |
| `state` | enum | `DRAFT` | `DRAFT` · `COMMITTED` · `ACCEPTED` · `DEPRECATED` |
| `priority` | enum | `medium` | `low` · `medium` · `high` · `critical` |
| `tags` | list | `[]` | Freeform tags for filtering |
| `secondary_actors` | list | `[]` | Other personas involved |
| `preconditions` | list | `[]` | What must be true before the journey starts |
| `auth_context.level` | enum | `public` | `public` · `authenticated` · `admin` · `service` |
| `auth_context.permissions` | list | `[]` | Required permissions, e.g. `["users:write"]` |
| `data_state.inputs` | list | `[]` | Data the journey receives |
| `data_state.persistent` | list | `[]` | Data the journey creates or modifies |
| `error_paths` | list | `[]` | Structured failure scenarios |
| `edge_cases` | list | `[]` | Race conditions, idempotency, security boundaries |
| `branches` | list | `[]` | Conditional/A-B flows |
| `depends_on` | list | `[]` | Prerequisite journey IDs |
| `extends` | string | `null` | Inherit steps from a base journey |
| `linked_stories` | list | `[]` | Associated story IDs |
| `linked_adrs` | list | `[]` | Associated ADR IDs |
| `implementation_summary` | object | `{}` | Top-level code mapping (populated post-implementation) |
| `test_hints` | object | `{}` | Test generation guidance |

## Step Schema

Each step in the `steps` list:

```yaml
- id: 1                             # Step number
  action: "User does X"             # What the user does
  system_response: "System does Y"  # What the system should do
  assertions:                       # Verifiable outcomes
    - "Expected result"
  data_changes:                     # Optional — data mutations
    - entity: "User"
      mutation: "created"
  implementation:                   # Optional — populated post-implementation
    routes: []                      # API/page routes this step touches
    files: []                       # Source files with type annotation
    tests: []                       # Test files that verify this step
```

### File Type Annotations

Use in `implementation.files[].type`:

`component` · `handler` · `service` · `model` · `middleware`

## Error Path Schema

```yaml
error_paths:
  - trigger_step: 2                 # Which step triggers the error
    condition: "Email taken"        # When it happens
    system_response: "Shows error"  # What the system does
    assertions:                     # Verifiable outcomes
      - "Error message displayed"
    severity: expected              # expected | warning | critical
```

## Edge Case Schema

```yaml
edge_cases:
  - scenario: "Double-submit"       # What happens
    expected: "Idempotent"          # Expected behavior
    severity: warning               # warning | critical
```

## Branch Schema

```yaml
branches:
  - condition: "SSO enabled"        # When to branch
    skip_steps: [2, 3]             # Steps to skip
    alternate_steps:               # Replacement steps
      - id: 2a
        action: "User clicks SSO"
        system_response: "Redirects to IdP"
        assertions: ["SSO session established"]
```

## Implementation Summary

Top-level aggregation populated after implementation:

```yaml
implementation_summary:
  entry_point: "/signup"            # Primary route or API endpoint
  components: []                    # All unique files across all steps
  test_suite: null                  # e.g. "tests/journeys/test_jrn_001.py"
```

## Test Hints

```yaml
test_hints:
  framework: pytest                 # pytest | jest | maestro | playwright
  type: integration                 # unit | integration | e2e
  fixtures:
    - name: "test_user"
      factory: "UserFactory"
  cleanup: true
```

## Full Example

```yaml
id: JRN-001
title: "User completes onboarding"
state: DRAFT
schema_version: 1
priority: medium
tags: [onboarding, auth]

actor: "unauthenticated user"
description: |
  New user signs up, verifies email, and completes profile setup.

preconditions:
  - "App is deployed and reachable"
  - "Email service is configured"

auth_context:
  level: public
  permissions: []

steps:
  - id: 1
    action: "User navigates to /signup"
    system_response: "Renders signup form"
    assertions:
      - "Signup form is visible"
      - "Submit button is disabled until valid"

  - id: 2
    action: "User submits email and password"
    system_response: "Creates account, sends verification email"
    assertions:
      - "HTTP 201 returned"
      - "Verification email sent"
    data_changes:
      - entity: "User"
        mutation: "created"

error_paths:
  - trigger_step: 2
    condition: "Email already registered"
    system_response: "Shows inline error, suggests login"
    assertions:
      - "Error message displayed"
      - "No duplicate account created"
    severity: expected

edge_cases:
  - scenario: "User double-submits signup form"
    expected: "Idempotent — no duplicate account"
    severity: warning

linked_stories: []
linked_adrs: [ADR-024]

implementation_summary:
  entry_point: "/signup"
  components: []
  test_suite: null
```
