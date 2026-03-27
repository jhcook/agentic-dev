# Platform Tools Reference

This document provides a detailed reference for the tools available to the AI agent, organized into consolidated domain modules as of INFRA-143.

## Project Module (`agent/tools/project.py`)

Tools for managing software development artifacts and repository workflows.

| Tool Name | Description | Key Arguments |
|-----------|-------------|---------------|
| `match_story` | Finds existing stories matching a description. | `query` |
| `read_story` | Retrieves the full text of a user story. | `story_id` |
| `read_runbook` | Retrieves the implementation plan for a story. | `story_id` |
| `list_stories` | Lists all stories in the repository cache. | `scope` (opt) |
| `list_workflows` | Lists available automation workflows. | - |
| `fix_story` | Interactive tool to remediate story inconsistencies. | `story_id` |
| `list_capabilities` | Lists all registered agent tools and signatures. | - |

**Project Management Examples**

```python
# Retrieve a story to understand requirements
story_content = read_story("INFRA-143")

# List all stories in the infra scope
infra_stories = list_stories(scope="infra")
