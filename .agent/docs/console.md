# Console Documentation

This document outlines the usage and features of the agentic-dev console.

## Features

* Agentic capabilities: The console now supports agentic workflows, allowing for more complex and automated tasks. Agentic mode is activated by using the `@role` command or the `/workflow` command. This triggers a continuous loop where the agent uses available tools to achieve a specified goal.
* CLI arguments:
  * `--model`: Specifies the language model to use for the console. Example: `agent console --model gpt-4`. This allows you to choose different language models for the agent's reasoning.
* In-console commands:
  * `/search <query>`: Searches the codebase for the specified query.
  * `/provider <provider>`: Sets the language model provider. Example: `/provider vertexai`
  * `/model <model>`: Sets the language model. Example: `/model gpt-4`
* UI improvements: Command history: The console now has command history, which you can navigate using the up and down arrow keys. This allows you to easily recall and reuse previous commands. The UI also features a panel that displays the agent's current thought process and actions during agentic workflows.
* Error handling guidance: Vertex AI authentication: If you encounter authentication issues with Vertex AI, ensure that you have correctly configured your `gcloud` settings and have the necessary permissions. See the project documentation for detailed steps.
* New agentic tools: The following tools are now available within the agentic workflow:
  * `read_file`: Reads the content of a file. Usage: `read_file(path="path/to/file")`
  * `edit_file`: Rewrites the entire content of a file. Use with caution. Usage: `edit_file(path="path/to/file", content="new file content")`
  * `patch_file`: Safely replaces a specific chunk of text in a file. Usage: `patch_file(path="path/to/file", search="text to replace", replace="replacement text")`
  * `run_command`: Executes a shell command within the repository. Usage: `run_command(command="command to execute")`
  * `find_files`: Finds files matching a glob pattern. Usage: `find_files(pattern="*.py")`
  * `grep_search`: Searches for a text pattern in the repository. Usage: `grep_search(pattern="pattern to search", path="path/to/search")`
* Continuous agentic mode: Activated by `@role` or `/workflow`, this mode allows the agent to continuously execute tasks until a final answer is reached. The UI features a panel that shows the agent's current thought process and actions.

## Data Handling and Privacy

By using the agentic features of this console, you acknowledge and agree that data from your local files and user prompts will be transmitted to third-party AI providers. Please do not use this feature with files containing personal, proprietary, or sensitive data unless you accept this risk.

## Troubleshooting

* Vertex AI Authentication Issues: Ensure that you have correctly configured your gcloud settings and have the necessary permissions.  See the project documentation for detailed steps and required roles. If you are still encountering issues, try running the following command: `gcloud auth application-default login`.

## Copyright

Copyright 2026 Justin Cook
