# AI Integration

The Agent Framework relies on LLMs for core logic.

## Supported Providers

### 1. Google Gemini (Recommended)
- **Model**: `gemini-1.5-pro`
- **Setup**:
  ```bash
  export GEMINI_API_KEY=your_key
  ```

### 2. OpenAI
- **Model**: `gpt-4o`
- **Setup**:
  ```bash
  export OPENAI_API_KEY=your_key
  ```

### 3. GitHub Models
- Used as a fallback if no key is provided.
- Requires `gh` CLI installed and authenticated.

## Context Window

The Agent automatically manages context, including:
- Active file content.
- Related ADRs.
- Project rules (`.agent/rules/`).
