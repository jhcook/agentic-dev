# Agent CLI - AI-Powered Governance Framework

> **Governance by Code**: Enforce architectural standards, compliance (SOC2/GDPR), and quality assurance through an intelligent CLI that acts as your development team's governance layer.

## 🚀 Overview

**Agent** is an AI-powered CLI tool that automates governance, compliance, and quality checks for software development teams. Think of it as your **virtual governance team** that:

- ✅ **Reviews code** for architecture violations
- ✅ **Enforces compliance** (GDPR, SOC2)
- ✅ **Validates test coverage** and documentation
- ✅ **Generates implementation plans** and runbooks
- ✅ **Automates preflight checks** before commits

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
```

## 📖 Documentation

- **[Deep Dive & Architecture](.agent/README.md)**: Detailed explanation of how the Agent framework works, including the AI Governance Panel, Synchronization, and Directory Structure.
- **[Full Documentation](docs/README.md)**: Comprehensive guides for all features.
  - [Getting Started](docs/getting_started.md)
  - [Commands Reference](docs/commands.md)
  - [Workflows](docs/workflows.md)
  - [Configuration](docs/configuration.md)
  - [Troubleshooting](docs/troubleshooting.md)

## 🤝 Contributing

See [docs/contributing.md](docs/contributing.md) for development setup and guidelines.

---

**Built with ❤️ for developers who care about quality**
