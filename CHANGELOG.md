# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Features
- **(INFRA-017)** Added `agent query "..."` command to ask natural language questions about the codebase. This feature uses a RAG pipeline to find relevant files, scrub them, and synthesize an answer with citations using an LLM.
- **(INFRA-023)** Added `agent config` command to manage configuration files via CLI. Supports `list`, `get`, and `set` operations with multi-file discovery, prefix routing (e.g., `agents.team.0.role`), dot-notation access, and automatic backups.
- **(INFRA-025)** Integrated Anthropic Claude 4.5 as a supported AI provider. Includes streaming support for large context windows (200K tokens), automatic fallback chain integration, and three model tiers: Claude Sonnet 4.5 (advanced), Claude Haiku 4.5 (standard), and Claude Opus 4.5 (premium). Configure with `ANTHROPIC_API_KEY` environment variable.

### Bug Fixes
- None.

### Changed
- None.