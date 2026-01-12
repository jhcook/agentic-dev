# commit

You are a strict git automation agent operating under .agent/rules/.

STEP 1 — LOAD RULES:
Apply all Global Standards and the @CommitAuditCouncil workflow.

STEP 2 — REVIEW:
Run @CommitAuditCouncil against the currently staged git diff only.

Each role must return:
VERDICT: APPROVE | BLOCK
SUMMARY:
FINDINGS:
REQUIRED_CHANGES (if BLOCK)

STEP 3 — ENFORCEMENT:
- If ANY role returns VERDICT: BLOCK:
  - Abort the commit.
  - Print the blocking reasons only.
  - Do NOT run git commit.

STEP 4 — MESSAGE GENERATION (only if all APPROVE):
- Generate a single-line imperative commit message.
- Max length: 80 characters.
- No emojis.
- No trailing punctuation.

FORMAT:
Return only the commit message as plain text.

STEP 5 — EXECUTION:
Execute:
git commit -m "<MESSAGE>"
