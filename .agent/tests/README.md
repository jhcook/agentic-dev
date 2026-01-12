# Agent Tests

Unit and integration tests for the `.agent` system utilities.

## Running Tests

### Run all agent tests:
```bash
cd .agent
pytest tests/
```

### Run specific test file:
```bash
pytest tests/test_count_tokens.py
```

### Run with coverage:
```bash
pytest tests/ --cov=lib --cov-report=html
```

### Run with verbose output:
```bash
pytest tests/ -v
```

## Test Structure

```
.agent/tests/
├── __init__.py              # Package marker
├── conftest.py              # Pytest fixtures and configuration
├── test_count_tokens.py     # Tests for token counting utility
└── README.md                # This file
```

## Requirements

Tests require pytest and tiktoken:

```bash
pip install pytest tiktoken
```

## Coverage Goals

- **count_tokens.py**: 100% coverage
  - Basic functionality
  - Edge cases (empty, unicode, large text)
  - Model fallback behavior
  - CLI interface

## Adding New Tests

1. Create new test file: `test_<module_name>.py`
2. Import the module under test
3. Write test classes and methods following pytest conventions
4. Use fixtures from `conftest.py` for common test data
5. Run tests to verify

## CI Integration

These tests are run as part of the governance preflight check. New code in `.agent/lib/` must include corresponding tests in `.agent/tests/`.
