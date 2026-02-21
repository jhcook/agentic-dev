# Agent Release & Upgrade Guide

This guide explains how to release new versions of the Agent CLI and how to configure target repositories to use the latest version in GitHub Actions.

## 1. Upgrading the Agent

To deploy the latest version of the Agent from `agentic-dev` to a target repository, use the `release.sh` script.

### Usage

```bash
./release.sh <absolute_path_to_target_repo>
```

### Example

```bash
./release.sh /Users/jcook/repo/agent/agent
```

### What `release.sh` Does

1. **Packages the Agent**: Runs `./package.sh` to create a `dist/agent-release.tar.gz` archive, ensuring all dependencies and the `pyproject.toml` are included.
2. **Deploys to Target**: Extracts the archive into the target repository's `.agent/` directory.
3. **Updates Workflow**: Automatically updates `.github/workflows/global-governance-preflight.yml` in the target repo to ensure it uses the correct installation command (`pip install .agent/[ai]`).

---

## 2. GitHub Actions Configuration

To use the embedded Agent in your CI/CD pipeline, ensure your GitHub Action is configured to install from the local `.agent` source.

### Recommended Workflow (`global-governance-preflight.yml`)

The following is the standard configuration for running AI Governance Preflight checks.

```yaml
name: Global Governance Preflight

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read
  pull-requests: write

jobs:
  governance:
    if: github.event.pull_request.draft == false
    name: Run .agent Preflight Governance
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Ensure agent CLI is executable
        run: chmod +x .agent/bin/agent

      # ... (Story Detection Logic) ...

      - name: Install Python dependencies
        run: |
          # CRITICAL: Install from the local .agent directory to get all dependencies
          pip install .agent/[ai]

      - name: Run Preflight Governance (AI Augmented)
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          AI_PROVIDER_PREFERENCE: gemini
        run: |
          # 1. Capture output to both log and file
          # 2. Use set +e to allow post-processing even on failure
          set +e 
          .agent/bin/agent preflight --story ${{ steps.story.outputs.story_id }} --ai --provider gemini --base ${{ github.base_ref }} --skip-tests --report-file preflight_results.json 2>&1 | tee governance_report.md
          EXIT_CODE=${PIPESTATUS[0]}
          echo "exit_code=$EXIT_CODE" >> $GITHUB_ENV
          exit $EXIT_CODE

      - name: Generate Governance Summary
        if: always()
        run: |
           # ... (See standard template for report generation logic) ...
```

### Key Configurations

* **Install Step**: Must used `pip install .agent/[ai]` (or `.agent` if AI is not needed) instead of listing packages manually. This ensures the CI environment matches the development environment defined in `pyproject.toml`.
* **Permissions**: Requires `pull-requests: write` to post the governance comment.
* **Secrets**: Ensure `OPENAI_API_KEY` or `GEMINI_API_KEY` are set in the repo secrets if using AI features.
