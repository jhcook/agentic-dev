# Release Process

The Agent CLI uses a **Git-driven release process**. The authoritative version is determined by the latest git tag.

## How to Release a New Version

### 1. Tag the Commit
Create an annotated git tag for the version you wish to release. We follow semantic versioning (e.g., `v1.2.0`).

```bash
# Syntax: git tag -a <version> -m "<release message>"
git tag -a v0.2.0 -m "Release v0.2.0: Major governance overhaul"
```

### 2. Push the Tag
Push the tag to the remote repository (GitHub) to trigger any CI/CD release workflows.

```bash
git push origin v0.2.0
```

## How Versioning Works

### Development Mode
When running from the source code (inside a git repository), the CLI dynamically resolves the version using:
```bash
git describe --tags --always --dirty
```
Example output: `v0.2.0-4-g9a2b` (4 commits after v0.2.0, hash g9a2b).

### Distribution Mode
When building a release artifact (tarball), the build script (`package.sh`) stamps the version into a static file:
`src/agent/VERSION`

This ensures that users installing the tool from a tarball (without `.git` metadata) still see the correct version when running:
```bash
agent --version
```
