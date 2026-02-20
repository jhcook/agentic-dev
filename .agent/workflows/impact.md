---
description: Perform impact analysis on code changes using the Agent's AI capabilities.
---

# Workflow: Impact Analysis

## PROCESS

1. **Run** `agent impact <STORY-ID>` for static dependency analysis.
2. **Add AI** with `agent impact <STORY-ID> --ai` for AI-powered risk assessment.
3. **Update story** with `agent impact <STORY-ID> --ai --update-story` to inject analysis.
4. **Compare branches** with `agent impact <STORY-ID> --base main`.
5. **JSON output** with `agent impact <STORY-ID> --json` for machine-readable results.

## FLAGS

| Flag | Description |
|------|-------------|
| `--ai` | Enable AI-powered risk assessment (default: static only) |
| `--base <branch>` | Compare against a specific branch (default: staged changes) |
| `--update-story` | Inject analysis into the story's Impact Analysis Summary section |
| `--json` | Output results as JSON |
| `--provider <name>` | Force AI provider (gh, gemini, vertex, openai, anthropic) |
| `--rebuild-index` | Force rebuild of the journey file index |

## OUTPUT

The command produces:

- **Static mode**: Dependency graph, reverse dependencies, component breakdown, affected journeys
- **AI mode**: Risk assessment, breaking changes, recommendations (plus all static output)
- **JSON mode**: Machine-readable report with all structured fields

## NOTES

- Do NOT run git commit after impact analysis
- Do NOT modify files unless `--update-story` is explicitly requested
- The `--ai` flag requires valid AI provider credentials
- Static analysis uses `DependencyAnalyzer` for objective dependency data
- AI adds contextual risk assessment and recommendations
