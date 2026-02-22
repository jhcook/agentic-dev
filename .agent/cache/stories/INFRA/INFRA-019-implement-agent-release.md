# INFRA-019: Implement Agent Release

## State
COMMITTED

## Problem Statement
Releasing new versions of the agent (or the project it manages) is a manual process involving editing `CHANGELOG.md`, bumping version numbers in multiple files (like `pyproject.toml`, `package.json`), and creating git tags. This is prone to human error (forgetting a file, malformed tags) and drift between the documented changes and actual commits.

## User Story
As a Release Manager, I want to run `env -u VIRTUAL_ENV uv run agent release [major|minor|patch]` to automate the version bumping, changelog generation, and tagging process, ensuring a consistent and compliant release artifact.

## Acceptance Criteria
- [ ] **SemVer Bump**: The command accepts a bump type (major, minor, patch) and updates the version in target files. Target files should be configurable (e.g., in `agent.yaml`), strictly defaulting to `package.sh` and `pyproject.toml`.
- [ ] **Pre-Release Verification**: Runs `env -u VIRTUAL_ENV uv run agent check` (linting/tests) *before* making any changes. Fails if checks fail, unless `--force` is provided.
- [ ] **Changelog Gen**: Scans git history since the last tag. Uses AI to summarize and *categorize* commits into "Added", "Fixed", "Changed", "Removed" sections (Keep a Changelog format).
- [ ] **Story Linkage**: The generated changelog explicitly links to the Story IDs (INFRA-XXX) found in the commit messages.
- [ ] **Git Tagging**: Commits changes and creates a git tag. Uses GPG signing (`git tag -s`) if a signing key is configured; otherwise falls back to annotated tags (`-a`).
- [ ] **Dry Run**: A `--dry-run` flag prints what *would* happen (new version, changelog text) without writing files or tags.

## Non-Functional Requirements
- **Safety**: The command must fail if the working directory is not clean (uncommitted changes).
- **Atomicity**: If any step fails (e.g. tagging), the system should attempt to rollback file changes to leave the repo in a clean state.
- **Audit**: The release action is logged to the `.agent/logs/` directory.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/release.py` (new), `agent/core/git_wrapper.py` (updates).
Workflows affected: Release Management.
Risks identified: AI hallucinating changelog entries (mitigated by explicit Story Linkage AC and manual review step).

## Test Strategy
- **Unit Tests**:
    - Version bump logic (SemVer parsing).
    - Changelog bucketing logic (mocking LLM response).
- **Integration Tests**:
    - Run `--dry-run` on the current repo and verify output correctness.
    - Test against a dirty working directory to verify failure.
    - Test the rollback mechanism by mocking a `git tag` failure.

## Rollback Plan
- Revert the commit and delete the git tag: `git tag -d vX.Y.Z && git reset --hard HEAD~1`.

