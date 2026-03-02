---
description: Review the most recent agent console session and provide UX feedback.
---

# Chat Session Review

1. **Run the CLI command**:

   ```bash
   agent review-chat
   ```

   - Use `--provider <name>` to specify an AI provider.
   - Use `--json` for machine-readable output (CI integration).

2. **Review the structured UX/ReAct feedback**:
   - The command analyzes the session across **Accuracy**, **Tone**, **Tool Usage**, and **Hallucination**.
   - Each category receives a rating with specific examples and recommendations.
   - Concrete suggestions for system prompt improvements are provided.

3. **Apply recommendations** (if needed):
   - Update `agent/tui/app.py` system prompts or tool schemas based on the feedback.

> **See Also**: `agent review-chat --help`
