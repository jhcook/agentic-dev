# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New `agent onboard` command to automate initial developer setup. This command handles dependency checks, API key configuration, and workspace initialization.
- New `agent visualize` command to generate Mermaid diagrams of project artifacts. Includes `graph` subcommand for full dependency graph and `flow` subcommand for single-story visualization. Supports `--serve` option for browser preview.

## [0.1.0] - 2023-10-26

### Added
- Initial project structure.
- Basic agent core logic.