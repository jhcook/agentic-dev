---
description: Run impact analysis on code changes using AI.
---
# Workflow: Impact Analysis

Run the following command:
`agent impact <STORY-ID> [--ai] [--base <BRANCH>] [--update-story]`

---

# Impact Analysis Guide

You are a Release Engineer performing an impact analysis.

## PURPOSE
To identify breaking changes, risks, and affected components before merging code.

## SYNTAX
```bash
agent impact <STORY-ID> [flags]
```

## FLAGS
- `--ai`: Enable AI-powered analysis (Required for deep insights).
- `--base <BRANCH>`: Compare against a specific branch (default: staged changes).
- `--update-story`: Automatically update the Story file with the analysis.

## PROCESS

1. **Identify the Story**:
   - Determine the Story ID from the context or user input.

2. **Run Analysis**:
   - Execute `agent impact <STORY-ID> --ai` to generate the report.
   - If you need to update the story file directly, append `--update-story`.

3. **Review Output**:
   - Check for **High Risks** or **Breaking Changes**.
   - If breaking changes are found, ensure they are documented in the Story and CHANGELOG.

## EXAMPLES

**Standard AI Analysis:**
```bash
agent impact INFRA-007 --ai
```

**Update Story with Analysis:**
```bash
agent impact INFRA-007 --ai --update-story
```

**Compare Branch vs Main:**
```bash
agent impact INFRA-007 --ai --base main
```
