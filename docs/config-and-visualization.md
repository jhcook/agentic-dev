# Commanding the AI Assembly Line: Configuration, Ingestion, and Visualization

In the "vibe coding" paradigm, an AI assistant is a black box. You paste code into a chat window, cross your fingers, and hope it understands your domain. If it hallucinates or applies the wrong design pattern, your only recourse is to painstakingly correct it across dozens of prompts.

`agentic-dev` rejects this. To operate at an enterprise level, you must treat your AI not as a stochastic chatbot, but as a deterministic assembly line. Like any precision manufacturing process, you need the ability to configure the machinery, inject precise raw materials, and instantly visualize the output.

This article explores how `agentic-dev` leverages **Configuration**, **Asset Importing**, and **Journey Visualization** to turn unpredictable AI generation into a rigid, manageable engineering workflow.

## 1. Zero to One: The `agent onboard` Command

Getting started with an enterprise toolchain usually involves days of reading documentation and manually copying boilerplate configurations. `agentic-dev` flips this script with the `agent onboard` command.

Running `agent onboard` instantly bootstraps your local repository for the Agentic workflow. It generates the necessary configuration files, initializes the `.agent` directory, and prompts you to select your preferred AI provider. Crucially, as detailed in our [Credential Security guide](credential-security.md), security is a first-class citizen by default. The onboarding process natively ties into your OS's secure keyring to ensure your API tokens and credentials are encrypted at rest from minute one, without ever relying on insecure plain-text `.env` variables.

You go from a raw repository to a fully governed, secure AI assembly line in seconds.

## 2. Global Governance: The `agent config` Command

An AI is only as context-aware as the guardrails you place around it. `agentic-dev` manages this through a centralized configuration system (`agent config`).

Instead of prepending instructions like "you are a senior backend developer" to every prompt, your repository maintains a persistent `.agent/etc/agent.yaml` configuration.

### Customizing the Panel
The system's core feature is the **AI Governance Panel**—a suite of parallel virtual developers (e.g., `@Architect`, `@Security`, `@QA`) that scrutinize code before it is committed. Through `agent config`, you explicitly define these personas and their strict evaluation parameters for *your* specific stack.

If your team mandates strict React Server Component usage, you update the `@Web` persona's configuration. From that moment on, every `agent implement` and `agent preflight` command naturally enforces those specific React patterns without human intervention. The configuration serves as a living, enforced architectural standard, actively rejecting AI-generated code that violates your team's specific guidelines.

## 3. Context Curation: The `agent import` System

The greatest weakness of Large Language Models is their training cutoff. If your company uses a bespoke internal CSS framework or a newly released API, the LLM will hallucinate.

`agentic-dev` neutralizes this via the `agent import` command, which allows you to seamlessly ingest external assets directly into the agent's contextual memory network.

### From Static Docs to Active Intelligence
Consider a scenario where you are integrating a new, poorly documented third-party payment API.
Instead of hoping the AI gets it right, you can ingest the provider's API specification:

```bash
agent import openapi --url https://api.payment-provider.com/v1/openapi.json
```

Or, if your team has a specialized internal design system guide:

```bash
agent import doc --path ./internal-docs/design-system.md
```

This is not a simple file copy. The `agent import` pipeline structure organizes these assets into the `.agent/cache/` environment. When you later run `agent new-runbook` to design the integration, the architecture governance panel autonomously consumes these imported assets, ensuring the generated implementation plan adheres strictly to the newly provided documentation.

You stop treating the LLM as an oracle and start treating it as a high-powered text processor that you feed with exactly the right specifications.

## 4. The Source of Truth: Managing and Visualizing Journeys

The fastest way to introduce regressions in AI-generated code is losing track of the user experience. To combat this, `agentic-dev` centralizes the UX contract into **User Journeys**—explicit YAML files defining the start state, user actions, and acceptance criteria.

### Lifecycle of a Journey
1. **Creation**: You create a journey (`agent new-journey <STORY_ID>`), anchoring an abstract business requirement to a concrete YAML file.
2. **Validation**: The build pipeline ensures no journey is malformed (`agent validate-journey`).
3. **Implementation**: The AI must map its code generation explicitly to satisfying these journeys.

However, as an application scales, managing dozens of YAML files becomes cognitively overwhelming.

### Real-Time Validation: `agent visualize flow`

To bridge the gap between human reasoning and AI-generated text files, `agentic-dev` provides instant diagrammatic translation via the `agent visualize flow` command.

When you run this command, the system parses your active User Journeys, ADRs (Architecture Decision Records), and Implementation Runbooks, instantly generating a dynamic, interactive Mermaid graph.

- **For Architecture**: You can visually inspect the exact component boundaries the AI intends to build before approving the PR.
- **For the UX**: You can verify that the generated YAML Journey accurately represents the required state transitions without having to manually read hundreds of lines of code.

## Conclusion: The Configurable Engine

The goal of `agentic-dev` is to shift the developer's role from writing boilerplate code to engineering the AI assembly line itself.

By mastering `agent config` to set boundaries, utilizing `agent import` to constantly feed the system accurate context, and relying on `agent visualize flow` to verify the outputs, you eliminate the guesswork. You stop vibe coding and start architecting a highly customized, profoundly capable AI development machine.
