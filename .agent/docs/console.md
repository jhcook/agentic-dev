# Console Documentation

This document outlines the usage and features of the `agentic-dev` console.

## Key Features

*   **Agentic Mode**: Triggered by invoking a role (`@<role>`) or a workflow (`/<workflow>`), the agent enters a continuous loop, using a suite of tools to achieve a specified goal until it reaches a final answer. The UI provides a real-time view of the agent's thoughts and actions.
*   **Agentic Continuation**: After an initial workflow or role-based task is complete, the agent remains in a tool-using mode, allowing for follow-up commands and iterative development without needing to re-invoke a role.
*   **Model & Provider Switching**: Easily switch between different LLM providers (e.g., `openai`, `vertexai`) and models (e.g., `gpt-4o`, `gemini-1.5-pro-latest`) on the fly using in-console commands.

## UI Interactions

*   **Command History**: Navigate your input history using the `Up` and `Down` arrow keys.
*   **Model Switching**: Click on a model name in the sidebar's "Models" panel to quickly switch the active LLM.

## Slash Commands

The console supports several commands for controlling its behavior:

*   `/search <query>`: Performs a quick, read-only search of the console's output panel.
*   `/provider <name>`: Sets the active LLM provider. Example: `/provider openai`
*   `/model <name>`: Sets the active LLM. The model must be compatible with the current provider. Example: `/model gpt-4o`
*   `/<workflow>`: Executes a predefined workflow. Workflows are defined in `.agent/workflows/`. Example: `/commit`

## Agentic Tools

The agent has access to a variety of tools to interact with the repository. For a complete and detailed list, please see the official [Tool Documentation](./agent_tools.md).

## Data Handling and Privacy

By using the agentic features of this console, you acknowledge and agree that data from your local files and user prompts will be transmitted to third-party AI providers. Please do not use this feature with files containing personal, proprietary, or sensitive data unless you accept this risk.

## Troubleshooting

*   **Vertex AI Authentication Issues**: Ensure you have correctly configured your `gcloud` settings and have the necessary permissions. If you still encounter issues, try running `gcloud auth application-default login`.

## Copyright

Copyright 2026 Justin Cook
