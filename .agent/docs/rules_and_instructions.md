# Rules & Instructions

Learn how to customize governance rules and role-specific instructions to fit your team's needs.

## Overview

The Agent CLI governance system is highly customizable through two main mechanisms:

1. **Rules** (`.agent/rules/`) - Global standards that apply to all code
2. **Instructions** (`.agent/instructions/`) - Role-specific guidance for AI agents

## Rules Directory Structure

The `.agent/rules/` directory follows a 100-based numerical indexing system to group rules logically:

```
.agent/rules/
├── 100-main.mdc                              # Core governance rules
├── 101-the-team.mdc                          # Team roles and responsibilities
├── 102-global-compliance-requirements.mdc    # SOC2, GDPR
├── 200-architectural-standards.mdc           # System design boundaries
├── 201-api-contract-validation.mdc           # API standards
├── 202-adr-standards.mdc                     # ADR creation guidelines
├── 203-state-enforcement.mdc                 # Workflow state transitions
├── 300-commit-workflow.mdc                   # Commit message rules
├── 301-anti-drift.mdc                        # Scope enforcement
├── 302-env-safety.mdc                        # Environment & test boundaries
├── 303-breaking-changes.mdc                  # Breaking changes policy
├── 400-lean-code.mdc                         # Code quality standards
├── 401-no-stubs.mdc                          # Stub prohibition
├── 402-colours.mdc                           # UI Brand and colours
├── 500-test.mdc                              # Testing requirements
├── 501-documentation.mdc                     # Documentation requirements
├── 502-license-header.mdc                    # License requirements
└── 600-mobile-platform-support.mdc           # Mobile OS support policy
```

## instructions Directory Structure

```
.agent/instructions/
├── compliance/
│   ├── GDPR.mdc                          # GDPR-specific checklist
│   └── SOC2.mdc                          # SOC2-specific checklist
└── qa/
    └── CRITICAL_FLOWS.mdc                # Critical E2E test requirements
```

## Creating Custom Rules

### Rule File Format

Every rule must be strictly self-documenting and follow this **Markdown Context (`.mdc`)** layout format to ensure precision for the AI parsing engine:

```markdown
---
description: A brief, single-sentence summary of the rule's purpose.
globs: ["**/*"] # Optional: specific files this rule applies to
alwaysApply: true # Optional: whether this rule applies regardless of glob
---

# [Rule ID]: [Rule Name]

## 1. Context & Purpose
Why does this rule exist? What specific problem or risk does it mitigate?

## 2. Requirements
The actionable directives that must be followed.
- **MUST**: Things that are strictly required.
- **MUST NOT**: Things that are strictly forbidden.

## 3. Examples
Concrete examples of compliance vs. violation.

### ✅ Good
\`\`\`python
def example():
    pass
\`\`\`

### ❌ Bad
\`\`\`python
def bad_example():
    pass
\`\`\`

## 4. Enforcement
Which agent persona (e.g., @Architect, @Security, @QA) is responsible for enforcing this rule? What is the penalty for violation (e.g., `VERDICT: BLOCK`)?
```

### Example: Creating a Performance Rule

```bash
# Create new rule file
cat > .agent/rules/403-performance.mdc << 'EOF'
---
description: Performance standards preventing blocking I/O in asynchronous backend flows.
globs: ["**/*.py"]
alwaysApply: true
---

# 403: Performance Standards

## 1. Context & Purpose
Blocking operations in async functions defeat the purpose of async/await in the Python backend, causing severe performance degradation and latency spikes across the API.

## 2. Requirements
- **MUST** use async alternatives (like asyncpg, aiohttp) for any I/O bound tasks in FastAPI endpoint routes.
- **MUST NOT** make synchronous requests, sleep, or run blocking ORM queries inside an `async def`.

## 3. Examples

### ✅ Good
\`\`\`python
async def fetch_user_data(user_id: str) -> dict:
    # Non-blocking database query
    user = await db.execute(select(User).where(User.id == user_id))
    return user.to_dict()
\`\`\`

### ❌ Bad
\`\`\`python
async def fetch_user_data(user_id: str) -> dict:
    # Blocking call in async function!
    user = db.query(User).filter_by(id=user_id).first()
    return user.to_dict()
\`\`\`

## 4. Enforcement
- **@Backend**: Evaluates endpoint signatures. `VERDICT: BLOCK` if synchronous I/O operations block an async route.
EOF
```

### Testing Your Rule

```bash
# Make some code changes
vim src/api/users.py

# Run preflight to see if rule is enforced
agent preflight --story BACKEND-001 --ai
```

The AI agents will now check your code against the new performance rules.

## Creating Role-Specific Instructions

Instructions provide additional context and checklists for specific governance roles.

### Instruction File Format

```markdown
# Instruction Category

Brief description of when these instructions apply.

## Checklist

- [ ] Checkpoint 1
- [ ] Checkpoint 2
- [ ] Checkpoint 3

## Reference Materials

Links to relevant documentation, ADRs, or external resources.

## Examples

Concrete examples of applying these instructions.
```

### Example: Adding Backend Instructions

```bash
# Create instructions directory
mkdir -p .agent/instructions/backend

# Create async/await best practices
cat > .agent/instructions/backend/async-patterns.md << 'EOF'
# Async/Await Best Practices

These instructions apply to all async Python code in the backend.

## Checklist

### Async Function Design
- [ ] All I/O operations use async libraries (aiohttp, asyncpg, etc.)
- [ ] No blocking calls (requests, time.sleep, etc.) in async functions
- [ ] Appropriate use of asyncio.gather for parallel operations
- [ ] Timeout configured for external calls

### Error Handling
- [ ] try/except blocks around async operations
- [ ] Graceful degradation on timeout
- [ ] Proper cleanup in finally blocks

### Testing
- [ ] Async tests use pytest-asyncio
- [ ] Mock async dependencies properly
- [ ] Test timeout scenarios

## Common Patterns

### Parallel API Calls
\`\`\`python
async def fetch_user_dashboard(user_id: str):
    # Good: Parallel execution
    user, posts, notifications = await asyncio.gather(
        fetch_user(user_id),
        fetch_user_posts(user_id),
        fetch_notifications(user_id),
    )
    return {"user": user, "posts": posts, "notifications": notifications}
\`\`\`

### Timeout Configuration
\`\`\`python
async def call_external_api():
    try:
        async with asyncio.timeout(5.0):  # 5 second timeout
            response = await client.get("https://api.example.com")
            return response.json()
    except TimeoutError:
        logger.warning("External API timeout")
        return None
\`\`\`

## Reference Materials

- [FastAPI Async Best Practices](https://fastapi.tiangolo.com/async/)
- ADR-015: Async/Await Patterns
- .agent/rules/403-performance.mdc
EOF
```

### Example: Adding Mobile Instructions

```bash
mkdir -p .agent/instructions/mobile

cat > .agent/instructions/mobile/offline-first.md << 'EOF'
# Offline-First Mobile Development

Mobile apps must be functional with poor or no network connectivity.

## Checklist

### Data Persistence
- [ ] AsyncStorage for simple key-value data
- [ ] SQLite for structured data
- [ ] Images cached locally

### Sync Strategy
- [ ] Queue mutations when offline
- [ ] Sync on reconnection
- [ ] Conflict resolution strategy defined
- [ ] User notified of sync status

### UI/UX
- [ ] Loading states for network operations
- [ ] Offline indicator visible
- [ ] Graceful error messages
- [ ] Optimistic UI updates

## Recommended Patterns

### Offline Queue
\`\`\`typescript
// Queue mutations when offline
const queueMutation = async (mutation: Mutation) => {
  if (!navigator.onLine) {
    await AsyncStorage.setItem(
      \`queue_\${Date.now()}\`,
      JSON.stringify(mutation)
    );
    return { status: 'queued' };
  }
  return await executeMutation(mutation);
};
\`\`\`

### Network Status Hook
\`\`\`typescript
import NetInfo from '@react-native-community/netinfo';

const useNetworkStatus = () => {
  const [isOnline, setIsOnline] = useState(true);
  
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      setIsOnline(state.isConnected ?? false);
    });
    return () => unsubscribe();
  }, []);
  
  return isOnline;
};
\`\`\`

## Reference Materials

- ADR-023: Offline-First Architecture
- [React Native NetInfo](https://github.com/react-native-netinfo/react-native-netinfo)
EOF
```

## Linking Rules and Instructions

Connect rules to instructions for comprehensive guidance:

**In rule file** (`.agent/rules/102-global-compliance-requirements.mdc`):

```markdown
## 2. Requirements
- **MUST NOT** commit raw secrets. See: `.agent/instructions/security/secrets-management.md`
```

**In instruction file** (`.agent/instructions/security/secrets-management.md`):

```markdown
# Secrets Management

This enforces the rule: .agent/rules/102-global-compliance-requirements.mdc → "No Secrets in Code"

## Approved Patterns

### Environment Variables
\`\`\`python
import os

API_KEY = os.environ['EXTERNAL_API_KEY']
\`\`\`

### Secrets Management Service
\`\`\`python
from vault import VaultClient

vault = VaultClient()
db_password = vault.get_secret('database/password')
\`\`\`
```

## Managing Compliance Rules

### GDPR Instructions

File: `.agent/instructions/compliance/GDPR.md`

```markdown
# GDPR Compliance Checklist

Use this checklist for any feature that collects, processes, or stores user data.

## Data Collection

- [ ] Lawful basis identified (consent, contract, legal obligation, etc.)
- [ ] User informed via privacy policy
- [ ] Consent mechanism implemented (if applicable)
- [ ] Data minimization principle followed
- [ ] Purpose limitation documented

## Data Storage

- [ ] Encryption at rest enabled
- [ ] Retention period defined
- [ ] Auto-deletion scheduled
- [ ] Access controls enforced

## Data Processing

- [ ] Processing purpose documented
- [ ] Third-party processors have DPA
- [ ] Data transfer safeguards (if international)

## User Rights

- [ ] Right to access: User can download their data
- [ ] Right to rectification: User can update their data
- [ ] Right to erasure: User can delete their data
- [ ] Right to portability: Data export in machine-readable format
- [ ] Right to object: User can opt-out of processing

## Documentation

- [ ] Privacy policy updated
- [ ] Data flow diagram created
- [ ] Record of processing activities updated

## References

- [GDPR Official Text](https://gdpr-info.eu/)
- .agent/compliance/GDPR.md
- Internal Privacy Policy
```

### SOC2 Instructions

File: `.agent/instructions/compliance/SOC2.md`

```markdown
# SOC2 Compliance Checklist

## Access Control (CC6.1)

- [ ] Least privilege principle applied
- [ ] Role-based access control (RBAC) implemented
- [ ] Access review process documented
- [ ] Former employee access revoked

## Audit Logging (CC7.2)

- [ ] All sensitive operations logged
- [ ] Logs include: timestamp, user, action, result
- [ ] Logs stored securely
- [ ] Log retention policy followed (minimum 1 year)

## Security Monitoring (CC7.3)

- [ ] Anomaly detection configured
- [ ] Alerts for suspicious activity
- [ ] Incident response plan documented
- [ ] Regular security reviews scheduled

## Data Protection (CC6.7)

- [ ] Encryption in transit (TLS 1.2+)
- [ ] Encryption at rest
- [ ] Secure key management
- [ ] Data backup and recovery tested

## Change Management (CC8.1)

- [ ] Changes reviewed and approved
- [ ] Testing in non-production environment
- [ ] Rollback plan documented
- [ ] Stakeholders notified

## References

- [SOC2 Framework](https://www.aicpa.org/soc)
- .agent/compliance/SOC2.md
```

## Best Practices

### 1. Start Small

Don't create 50 rules on day one. Start with:

- Critical security rules (no secrets, no PII)
- Architectural boundaries
- Test coverage requirements

Add more rules as your team matures.

### 2. Be Specific

**❌ Vague:**

```markdown
## Code should be good quality
Write clean, maintainable code.
```

**✅ Specific:**

```markdown
---
description: Functions must declare proper type hints.
---

# 404: Type Hints Required

## 1. Context & Purpose
All public functions must have type hints for parameters and return values to improve safety and DX.

## 3. Examples

### ✅ Good
\`\`\`python
def calculate_total(items: List[Item]) -> Decimal:
    return sum(item.price for item in items)
\`\`\`

### ❌ Bad
\`\`\`python
def calculate_total(items):
    return sum(item.price for item in items)
\`\`\`
```

### 3. Provide Examples

Every rule should have:

- ✅ Good example (correct implementation)
- ❌ Bad example (common violation)
- 🔧 How to fix (if not obvious)

### 4. Link to ADRs

For architectural rules, reference relevant ADRs:

```markdown
## BLOCKER: Use PostgreSQL for Relational Data

See: ADR-003 - Database Technology Selection

SQLite is not approved for production use.
```

### 5. Update After Incidents

When bugs occur:

1. Root cause analysis
2. Create/update rule to prevent recurrence
3. Add instruction for how to avoid

Example:

```markdown
---
description: Ensure all user input is validated before processing to prevent SQL injection.
---

# 103: Validate All User Input

## 1. Context & Purpose
Added after SEC-2026-001 (SQL injection vulnerability). All user-provided data must be validated before processing to prevent arbitrary code execution or invalid state.
```

### 6. Version Control Everything

Rules and instructions are code:

- Commit changes with meaningful messages
- Review changes in PRs
- Document breaking changes in CHANGELOG

### 7. Test Rule Changes

Before merging rule changes:

```bash
# Test against existing code
agent preflight --story INFRA-001 --ai

# Test against new development
agent preflight --story WEB-042 --ai
```

## Advanced: Dynamic Rules

For complex scenarios, you can use conditional logic in your instructions:

```markdown
# Database Migration Rules

## If Adding a New Table

- [ ] Migration script created
- [ ] Rollback script tested
- [ ] Indexes defined
- [ ] Foreign key constraints validated

## If Modifying Existing Table

- [ ] Migration is backward-compatible
- [ ] No data loss
- [ ] Deployment strategy allows for rolling updates
- [ ] ADR created for schema changes

## If Deleting a Table

- [ ] BLOCKER: ADR required
- [ ] Data archived if needed
- [ ] All references removed from code
- [ ] Deployment coordinated with team
```

## Maintaining Rule Quality

### Regular Review Schedule

- **Monthly**: Review governance logs for common violations
- **Quarterly**: Team retro on rule effectiveness
- **Annually**: Comprehensive rule audit

### Metrics to Track

```bash
# Parse preflight logs
grep "BLOCKER" .agent/logs/preflight-*.log | wc -l
grep "WARNING" .agent/logs/preflight-*.log | wc -l

# Most common violations
grep "BLOCKER" .agent/logs/preflight-*.log | \
  cut -d':' -f3 | sort | uniq -c | sort -rn
```

### Rule Lifecycle

1. **Proposed** - New rule suggested
2. **Trial** - Rule active with WARNING severity
3. **Enforced** - Rule upgraded to BLOCKER
4. **Deprecated** - Rule no longer relevant
5. **Archived** - Moved to `.agent/rules/archive/`

---

**Next**: [Configuration](configuration.md) →
