---
description: Review the most recent voice agent session and provide UX feedback.
---

# Voice Session Review

1. **Run the CLI command**:

   ```bash
   agent review-voice
   ```

   - Use `--provider <name>` to specify an AI provider.
   - Use `--json` for machine-readable output (CI integration).

2. **Review the structured UX feedback**:
   - The command analyzes the session across **Latency**, **Accuracy**, **Tone**, and **Interruption**.
   - Each category receives a rating with specific examples and recommendations.
   - Concrete suggestions for `voice_system_prompt.txt` or `voice.yaml` are provided.

3. **Apply recommendations** (if needed):
   - Update `voice_system_prompt.txt` or `voice.yaml` based on the feedback.

> **See Also**: `agent review-voice --help`
