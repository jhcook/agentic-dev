# Agentic Console TUI

The Agentic Console is a powerful, interactive terminal user interface (TUI) for interacting with AI models, executing local tools, and managing your development workflow.

## Overview

The console provides a rich chat-like interface with special capabilities invoked by slash commands (`/`) and an agentic tool-calling loop for complex tasks.

## Layout

1. **Chat History**: The main area displays the conversation history, including your prompts, AI responses, tool calls, and tool outputs.
2. **Input Bar**: Where you type your messages and commands. It supports multi-line input (`Shift+Enter` for newlines) and command history (`Up`/`Down` arrows).
3. **Sidebars**: Collapsible panels for quick selection:
   - **Model Selector (`CTRL+N`)**: Lists preferred and available AI models. Clicking a model instantly switches the active AI provider and model for the current session.
   - **Workflows (`CTRL+W`)**: Lists available agentic workflows (e.g., `/pr`, `/implement`).
   - **Roles (`CTRL+R`)**: Lists available AI personas/roles (e.g., `@Architect`, `@Security`).
4. **Execution Output Panel**: A specialized panel that slide-up to display the real-time, line-by-line output of commands executed by the agent. It automatically hides when tool execution completes.
5. **Status Bar**: Shows the current model, token usage, and other contextual information.

> [!NOTE]
> **Synchronization**: Provider and model changes are synchronized across your active session and persist when switching conversations or creating new ones.
> **Clean Thoughts**: The console agent's internal reasoning (ReAct loop) is filtered to show only human-readable "thoughts," hiding raw JSON or internal protocol logs.

## UI Layout Diagram

```text
┌──────────────────────────────────────────┐
│ [MODELS] [ROLES] [WORKFLOWS]             │
│   (Sidebar Panels - Collapsible)         │
├─────────────────┬────────────────────────┤
│                 │                        │
│  Model Selector │    Chat History        │
│    (Sidebar)    │   (Main Output context)│
│                 │                        │
│                 │                        │
│                 ├────────────────────────┤
│                 │  [EXECUTION LOG]       │
│                 │  (Live Tool Output)    │
├─────────────────┴────────────────────────┤
│ > [Input Bar: type /help]                │
├──────────────────────────────────────────┤
│ Provider: gemini | Model: 2.0 Pro | 0/128k│
└──────────────────────────────────────────┘
```

## Key Features

### 1. Agentic Tool Use

Invoking the agent allows the AI to use a suite of local tools to perform tasks on your repository, such as reading/writing files and running commands.

- **How to invoke**: Start your prompt with `/agent` or `/do`.
- **Example**: `/agent read the README.md file and summarize it`

Available tools include:
- `read_file(path)`: Reads a file from the repository.
- `edit_file(path, content)`: Writes content to a file.
- `run_command(command)`: Executes a shell command. Output is **streamed line-by-line** to the execution output panel in real-time.
- `find_files(pattern)`: Finds files using a glob pattern.
- `grep_search(pattern, path)`: Searches for text within files.

### 2. Standard Chat

If you enter a prompt without a special command prefix, it is treated as a standard chat query. The AI will respond directly without using tools. This is useful for quick questions, code generation, or general conversation.

### 3. Search and Navigation

The `/search` command uses the `agent search` engine to find relevant code snippets.
- **Navigation**: While search results are displayed, use the `n` key for the next match and `r` for the previous (reverse) match.

### 4. Session Persistence

The console automatically saves your conversation history. If you exit and restart the console, you can resume your previous session with all context intact.

### 5. Disconnect Recovery

If a network error occurs during a stream, the console provides a Disconnect Recovery modal. You can choose to:
- **Retry**: Attempt to resend the last prompt.
- **Switch Provider**: Quickly switch to an alternative AI provider (e.g., from Vertex to direct Gemini) and retry.
- **Cancel**: Preserve the partial response and continue manually.

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `CTRL+N` | Toggle Model Selector Sidebar |
| `CTRL+W` | Toggle Workflows Sidebar |
| `CTRL+R` | Toggle Roles Sidebar |
| `CTRL+Q` | Quit Application |
| `CTRL+X` | Clear Chat Output |
| `CTRL+L` | Show Application Log |
| `CTRL+C` (in output) | Copy selected text to clipboard |
| `Shift+Enter` | Insert newline in Input Bar |
| `Up / Down` | Navigate command history |

## Commands

All special commands start with a forward slash (`/`).

- **/help**: Displays a list of available commands.
- **/tools**: Lists all available agentic tools and their descriptions.
- **/model `<MODEL_ID>`**: Switch the AI model.
- **/search `<QUERY>`**: Performs a semantic search across your codebase.
- **/copy**: Copies the content of the last message block to the clipboard.
- **/log**: View the application log.
- **/quit** or **/exit**: Exits the console application.

## Launching the Console

To start the console, run the following command from your terminal:

```bash
agent console
```

### Model Selection Flag

You can start the console with a specific model pre-selected using the `--model` flag.

```bash
agent console --model gpt-4o
```

## Copyright

Copyright (c) 2026 Justin Cook
