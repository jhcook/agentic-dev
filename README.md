# Agent CLI - AI-Powered Governance Framework

> **Governance by Code**: Enforce architectural standards, compliance (SOC2/GDPR), and quality assurance through an intelligent CLI that acts as your development team's governance layer.

## 🚀 Overview

**Agent** is an AI-powered CLI tool that automates governance, compliance, and quality checks for software development teams. Think of it as your **virtual governance team** that:

- ✅ **Reviews code** for architecture violations
- ✅ **Enforces compliance** (GDPR, SOC2)
- ✅ **Validates test coverage** and documentation
- ✅ **Generates implementation plans** and runbooks
- ✅ **Automates preflight checks** before commits

## 🛑 Validation vs 💡 Consultation

The Agent supports two modes of governance review:

### 1. Preflight (The Gatekeeper)
**Command**: `agent preflight --ai`
- **Role**: Strict auditor.
- **Goal**: Validation before merge/deploy.
- **Outcome**: `PASS` or `BLOCK` (Exit code 1 on failure).
- **Use When**: You are ready to commit or create a PR.

### 2. Panel (The Expert Council)
**Command**: `agent panel` (or via workflow)
- **Role**: Expert consultants (Architect, Security, QA).
- **Goal**: Advice, warnings, and design feedback.
- **Outcome**: Friendly advice (Always exit code 0).
- **Use When**: You are designing, prototyping, or stuck.

## ⚡ Quick Start

### Prerequisites
- Python 3.9+
- Git
- `pip`
- `shellcheck` (for shell scripts)
- `npm` (for JS/TS)

### Installation

```bash
# Clone the repository
git clone <your-repo>
cd <your-repo>

# Install dependencies
pip install -r .agent/requirements.txt
# Note: Ensure shellcheck and npm are installed for full functionality.

# Add to PATH
export PATH="$PATH:$(pwd)/.agent/bin"

# Initialize
agent new-story

## 🛠️ Key Commands

- `agent run-ui-tests`: Run Maestro UI tests.
- `agent preflight`: Run governance checks.
- `agent panel`: Consult with AI experts.
- `agent lint`: Run linters.
```

## 📖 Documentation

- **[Deep Dive & Architecture](.agent/README.md)**: Detailed explanation of how the Agent framework works.
- **[Full Documentation](.agent/docs/README.md)**: Comprehensive guides for all features.
  - [Getting Started](.agent/docs/getting_started.md)
  - [Commands Reference](.agent/docs/commands.md)
  - [Workflows](.agent/docs/workflows.md)
  - [Configuration](.agent/docs/configuration.md)
  - [Troubleshooting](.agent/docs/troubleshooting.md)

## 🤝 Contributing

See [docs/contributing.md](docs/contributing.md) for development setup and guidelines.

---

**Built with ❤️ for developers who care about quality**
