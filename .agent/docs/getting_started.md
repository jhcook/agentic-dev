# Getting Started

## Installation

The Agent Framework is included in the repo. To install dependencies:

```bash
pip install -e .agent/
```

## Setup

1.  **Environment Variables**:
    Copy `.env.example` to `.env` and set your keys:
    ```bash
    cp .env.example .env
    ```
    Required:
    - `GEMINI_API_KEY`: For the main AI logic.
    - `SUPABASE_ACCESS_TOKEN`: For artifact synchronization.

2.  **Verify Installation**:
    ```bash
    agent --help
    ```

## Your First Story

The Agent workflow is driven by "Stories".

1.  **Create a Story**:
    ```bash
    agent new-story "Refactor login logic"
    ```
    This creates a file in `.agent/cache/stories/`.

2.  **Generate a Runbook**:
    Once your story is defined, generate a runbook:
    ```bash
    agent new-runbook STORY-001
    ```

3.  **Run Preflight**:
    Before coding, check for governance compliance:
    ```bash
    agent preflight --story STORY-001
    ```
