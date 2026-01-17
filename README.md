# Project Agent

Welcome to the Project Agent repository. This agent is designed to automate complex tasks.

## Quick Start

Getting started is simple. Use the automated onboarding command to set up your environment in minutes.

## Tooling

### Visualize Project Artifacts

Generate Mermaid diagrams of your governance artifacts (Plans, Stories, Runbooks):

```bash
# Generate full dependency graph (outputs Mermaid syntax)
agent visualize graph

# Generate graph and serve in browser
agent visualize graph --serve

# Visualize a specific story's flow
agent visualize flow INFRA-016
```

1.  **Clone the repository:**