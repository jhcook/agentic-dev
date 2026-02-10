.PHONY: test test-unit test-all sync lint

# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────

sync: ## Install/sync all default + optional deps
	uv sync --extra ai --extra admin

sync-all: ## Install ALL optional deps (requires platform support)
	uv sync --extra ai --extra admin --extra voice

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

test: ## Run all tests (optional-dep tests auto-skip when deps missing)
	uv run pytest tests/ -x --tb=short

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -x --tb=short

test-all: ## Run full suite including voice (requires --extra voice)
	uv run pytest tests/ -x --tb=short

# ──────────────────────────────────────────────
# Code Quality
# ──────────────────────────────────────────────

lint: ## Run ruff linter
	uv run ruff check src/ tests/

lint-fix: ## Run ruff linter with auto-fix
	uv run ruff check --fix src/ tests/

# ──────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────

preflight: ## Run governance preflight checks
	uv run agent preflight

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
