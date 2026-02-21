---
description: Create a new user story.
---

# Workflow: Create Story

Run the following command:
`agent new-story <STORY-ID>`

- By default, the AI will prompt for context and generate a populated story draft.
- You can provide the context inline: `agent new-story <STORY-ID> --prompt "Context for the story"`
- Alternatively, you can disable AI generation and manually populate the file:
`agent new-story <STORY-ID> --offline`

If you used `--offline`, you must manually populate the generated file with details from the current conversation including:

- Problem Statement
- User Story
- Acceptance Criteria
