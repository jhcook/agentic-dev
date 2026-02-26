# Agent Console — Terminal TUI

Interactive terminal interface for AI-assisted development, powered by [Textual](https://textual.textualize.io/).

## Quick Start

```bash
# Install with console extras
pip install 'agent[console]'

# Launch
agent console

# Launch with a specific provider
agent console --provider vertex
```

## Layout

```
┌─────────────────────────────┬─────────────┐
│                             │  Workflows  │
│        Chat Panel           ├─────────────┤
│                             │    Roles    │
├─────────────────────────────┴─────────────┤
│  Provider: gemini │ Model: gemini-2.5-pro │
├───────────────────────────────────────────┤
│  Type a message…                          │
└───────────────────────────────────────────┘
```

- **Chat Panel** — AI conversation with token-by-token streaming.
- **Workflows sidebar** — Click to insert `/workflow` commands.
- **Roles sidebar** — Click to insert `@role` prefixes.
- **Status bar** — Active provider, model, and token usage.
- **Input box** — Type messages, commands, or select from sidebars.

## Commands

| Command | Description |
|---|---|
| `/help` | Show all available commands |
| `/new` | Start a new conversation |
| `/conversations` | List saved conversations |
| `/history` | Alias for `/conversations` |
| `/switch <n>` | Switch to conversation number n |
| `/delete` | Delete a conversation |
| `/rename <title>` | Rename the current conversation |
| `/clear` | Clear the chat display |
| `/provider [name]` | Show or switch AI provider |
| `/model [name]` | Set model override |
| `/quit` | Exit the console |

## Workflows & Roles

Click a workflow or role in the sidebar to insert it into the input box:

- **Workflows** (e.g. `/commit`, `/preflight`, `/pr`) — discovered from `.agent/workflows/`.
- **Roles** (e.g. `@architect`, `@security`) — discovered from `.agent/etc/agents.yaml`.

Clicking inserts the prefix and places the cursor after it, ready for you to type your question.

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Tab` | Switch between panels |
| `↑` / `↓` | Navigate list items |
| `Enter` | Send message or select item |
| `Ctrl+C` | Exit |

## Streaming

Responses stream token-by-token using `AIService.stream_complete()`. Supported providers:

| Provider | Streaming |
|---|---|
| Gemini / Vertex | ✅ Native (`generate_content_stream`) |
| Anthropic | ✅ Native (`messages.stream`) |
| OpenAI / Ollama | ✅ Native (`stream=True`) |
| GH CLI | ⚠️ Single-chunk fallback |

## Session Persistence

Conversations are stored in `.agent/cache/console.db` (SQLite):

- File permissions: `0600` (user-only read/write)
- Auto-titles from first message
- Full message history preserved across restarts
- FIFO token pruning keeps context within budget

## Disconnect Recovery

If the AI provider disconnects mid-response, a modal appears with options:

- **Retry** — Resend the last message to the same provider.
- **Switch Provider** — Fail over to the next available provider.
- **Cancel** — Discard and return to the input.

## Copyright

Copyright 2026 Justin Cook
