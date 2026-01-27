---
description: Review the most recent voice agent session and provide UX feedback.
---

# Voice Session Review

1. **Fetch History**
   - Run the fetch script:

     ```bash
     python3 .agent/scripts/fetch_last_session.py
     ```

2. **Analyze Conversation**
   - If the output is an error (or empty), inform the user that no active session was found.
   - If history exists, analyze it for:
     - **Latency**: Did the user have to repeat themselves?
     - **Accuracy**: Did the agent misunderstand intent?
     - **Tone**: Was the agent helpful and concise (as per `voice_system_prompt.txt`)?
     - **Interruption**: Did the agent interrupt the user inappropriately?

3. **Provide Feedback**
   - Summarize the session.
   - Provide concrete recommendations to improve the `voice_system_prompt.txt` or `voice.yaml` config.
