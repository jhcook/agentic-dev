---
description: Perform impact analysis on code changes using the Agent's AI capabilities.
---

# Workflow: Impact Analysis

You will manually perform the impact analysis logic instead of running the CLI command.

## PROCESS

1. **Identify Story ID**:
   - Determine the Story ID from the context or user input.

2. **Get Git Diff**:
   - If a base branch is provided (e.g., via User Request "compare against main"), run:
     `git diff <BASE>...HEAD .`
   - Otherwise, get the staged changes:
     `git diff --cached .`
   - If the output is empty, notify the user.

3. **Read Story Context**:
   - Locate the story file: `.agent/cache/stories/*/<STORY-ID>*.md`.
   - Read its content using `read_file`.

4. **Generate AI Analysis**:
   - Construct a prompt including the **Story Content** and the **Git Diff**.
   - Use the `notify_user` tool (or just plain text output) to generate the analysis.
   - **PROMPT**:
     ```
     You are an expert Release Engineer. Analyze these changes:
     
     STORY:
     <Story Content>
     
     DIFF:
     <Git Diff>
     
     Determine:
     1. Components touched
     2. Workflows affected
     3. Risks (Security, Performance, etc.)
     4. Breaking Changes
     
     Provide a "Impact Analysis Summary".
     ```

5. **Update Story (Optional)**:
   - If the user requested to update the story (e.g., "update the story"), use `replace_file_content` to inject the analysis into the "Impact Analysis Summary" section of the story file.

6. **Report**:
   - Output the analysis to the user.

NOTES:
- Do NOT run git commit.
- Do NOT modify files.
- Focus only on analysis and feedback.