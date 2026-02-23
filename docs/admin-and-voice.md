# Admin and Voice: Visibility and Feedback Loops

Just as the `agentic-dev` framework brings rigorous, deterministic workflows to software engineering, it also provides robust, built-in tools for **visibility** and **continuous improvement**. These capabilities are encapsulated in two dedicated modules: the Admin Console and the Voice UX Analyst.

Both of these features are packaged natively within the compiled `agent` executable. By simply deploying the `.agent/bin/agent` binary into a repository, engineering teams instantly inherit a local web dashboard for project management and a self-improving feedback loop for their voice workflows.

## The Admin Console (`agent admin`)

While `.agent/etc/*.yaml` files and markdown runbooks serve as the deterministic source of truth, reading raw configuration files isn't always the fastest way to understand a project's state. The Admin module solves this by providing a local, graphical web interface that brings your YAML configurations and agentic workflows to life.

### Background Operation
The Admin Console is designed to run silently as a background service. When an engineer executes `agent admin start`, the binary automatically orchestrates two detached subprocesses:
1. **Backend API**: A FastAPI Uvicorn server (defaulting to port `8000`).
2. **Frontend UI**: A React/Vite development server (defaulting to port `8080`).

Because these processes are detached, the CLI immediately returns control of the terminal to the developer. The web console remains running in the background until explicitly stopped via `agent admin stop`.
*(Note: For debugging or live monitoring, developers can attach their console to the live logs using `agent admin start --follow`).*

By centralizing visibility into a zero-configuration local server, teams can visually manage and interact with their projects without relying on external SaaS tools or cloud dashboards.

## The Voice UX Analyst (`agent review-voice`)

As developers increasingly rely on voice interfaces to interact with AI agents (e.g., orchestrating story generation or brainstorming architectural decisions), the quality of that user experience (UX) becomes critical. The `agent review-voice` module implements a programmatic feedback loop designed specifically to analyze and improve these voice interactions.

Unlike the background Admin service, the Voice Review tool runs synchronously in the foreground, providing immediate, actionable insights exactly when you need them.

### Privacy-First Analytics
When a developer runs `agent review-voice`, the CLI executes a strictly deterministic and privacy-conscious workflow:
1. **Retrieval**: It fetches the raw transcript of the most recent voice interaction.
2. **Sanitization**: It aggressively scrubs the transcript of sensitive data, API keys, and credentials to ensure compliance with privacy design principles and GDPR lawful bases (e.g., Art. 6(1)(f) for UX improvement).
3. **AI Evaluation**: It submits the sanitized transcript to the configured AI provider (such as Gemini, Vertex, OpenAI, or Anthropic) using a strict analytical prompt. The AI acts in the persona of a Voice UX Analyst.
4. **Structured Feedback**: The tool outputs a detailed, formatted UX report directly to the terminal.

### The Four Pillars of Review
The AI analyst evaluates the voice session across four specific quality categories:

* **Latency**: Did the system exhibit long pauses, or did the user have to repeat themselves?
* **Accuracy**: Did the agent correctly interpret the user's intent and provide factually sound responses?
* **Tone**: Was the interaction concise, helpful, and naturally aligned with the system's behavioral guidelines?
* **Interruption**: Were turn-taking signals handled gracefully without inappropriate interruptions or cutoff sentences?

For each category, the analyst assigns a concrete rating (**EXCELLENT**, **GOOD**, **NEEDS IMPROVEMENT**, or **POOR**), provides specific transcript examples to support the rating, and lists actionable recommendations for tweaking the `voice_system_prompt.txt` or `.agent/etc/voice.yaml` configuration to improve future sessions.

## The Power of the Compiled Binary

By shipping these robust tools directly inside the standalone `agent` binary, the `agentic-dev` framework ensures that powerful management dashboards and sophisticated UX feedback loops are entirely portable.

When you adopt the framework in a new repository via the `release.sh` workflow, there are no complicated Node.js dependencies to install, no Python virtual environments to manage, and no configuration servers to spin up. You simply get pure, executable visibility and continuous UX refinement right out of the box.
