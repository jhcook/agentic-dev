# Implementation Engine

The Implementation Engine handles the application of code changes from generated runbooks to the local workspace. It operates in two primary phases: application and verification.

## Validation Gates

To maintain code quality and security standards, every file modification or creation passes through a series of validation gates. Gates now support three severity levels:

| Level | Description | Behavior |
| :--- | :--- | :--- |
| **Pass** | No violations detected. | File is written to disk. |
| **Warning** | Non-critical violations (e.g., missing docstrings in tests). | File is written to disk; a warning is logged. |
| **Fail** | Critical violations (e.g., syntax errors, security risks). | File is rejected; implementation is marked incomplete. |

## Docstring Validator

The docstring gate ensures that all new functions and classes include proper documentation. However, to prevent unnecessary friction, specific patterns are downgraded to `Warning` severity.

**Exclusion Patterns**

The following file patterns trigger warnings instead of failures when docstrings are missing:

- **Test Files**: Files following standard testing conventions:
  - `test_*.py` / `*_test.py` (Python)
  - `*.test.*` / `*.spec.*` (JavaScript/TypeScript)
- **Module Initializers**: `__init__.py` files.
- **New Files**: Non-test source files (`[NEW]`) with documentation gaps are written to disk but flagged as success-with-warnings to ensure developers can review logic immediately.

## Observability

When `agent implement` completes, the system provides a summary banner based on the highest severity encountered:

- **SUCCESS**: All files passed all gates.
- **SUCCESS WITH WARNINGS**: All files were written, but some triggered non-critical warnings.
- **INCOMPLETE IMPLEMENTATION**: One or more files were rejected due to hard failures.

## Troubleshooting

If a file is missing from your workspace after an implementation run:
1. Check the CLI output for any `REJECTED` entries.
2. Review the validation error message; if it is a syntax error or security violation, the gate correctly blocked the write.
3. Check `.agent/src/agent/core/implement/engine.py` for logic updates regarding `rejected_files` collection.
