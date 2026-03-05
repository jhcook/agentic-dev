# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **INFRA-095**: Implemented micro-commit implementation loop and circuit breaker in `implement.py`.
  - Added line-level edit distance tracking per implementation step.
  - Added save-point micro-commits after each successful runbook step application.
  - Implemented 200 LOC warning and 400 LOC hard circuit breaker for implementation runs.
  - Added automatic follow-up story generation and plan linkage when the circuit breaker is triggered.
  - Integrated OpenTelemetry spans for micro-commit steps and circuit breaker events.

### Fixed
- N/A

### Changed
- Refactored `agent implement` chunked processing loop to support atomic save points and size enforcement.