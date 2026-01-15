# Governance System

The Agent Framework enforces "Governance by Code".

## The Panel

Each change is reviewed by a virtual panel of AI agents:

- **@Architect**: Ensures alignment with ADRs.
- **@Security**: Checks for secrets, PII, and injection risks.
- **@QA**: Verifies test coverage and strategy.
- **@Compliance**: Checks against SOC2 and GDPR rules.
- **@Product**: Validates acceptance criteria.

## Rules

Rules are defined in `.agent/rules/`. These are markdown files that provide context to the AI agents.
- `tech-stack.mdc`: Technology choices.
- `coding-standards.mdc`: Style guides.

## Compliance

### PII Scrubbing
All text sent to AI providers or stored in the local cache is passed through a scrubber (`agent.core.utils.scrub_sensitive_data`) to remove:
- Emails
- IP Addresses
- API Keys

### Data Persistence
Local artifacts are stored in `.agent/cache/agent.db` (SQLite). This data is scrubbed of PII.
Remote synchronization uses Supabase for encrypted storage.
