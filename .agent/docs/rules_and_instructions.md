# Rules & Instructions

Learn how to customize governance rules and role-specific instructions to fit your team's needs.

## Overview

The Agent CLI governance system is highly customizable through two main mechanisms:

1. **Rules** (`.agent/rules/`) - Global standards that apply to all code
2. **Instructions** (`.agent/instructions/`) - Role-specific guidance for AI agents

## Rules Directory Structure

```
.agent/rules/
├── main.mdc                              # Core governance rules
├── adr-standards.mdc                     # ADR creation guidelines
├── api-contract-validation.mdc           # API standards
├── commit-workflow.mdc                   # Commit message rules
├── documentation.mdc                     # Documentation requirements
├── global-compliance-requirements.mdc    # SOC2, GDPR
├── lean-code.mdc                        # Code quality standards
├── state-enforcement.mdc                  # Workflow state transitions
├── test.mdc                             # Testing requirements
└── the-team.mdc                         # Team roles and responsibilities
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

Rules are written in **Markdown Context (`.mdc`)** format:

```markdown
# Rule Category Name

## Severity Level: Rule Name

Description of the rule and why it exists.

### Examples

**✅ Good:**
\`\`\`python
# Example of correct implementation
def get_user(user_id: str) -> User:
    """Get user by ID."""
    return db.query(User).filter_by(id=user_id).first()
\`\`\`

**❌ Bad:**
\`\`\`python
# Example of violation
def get_user(user_id):  # Missing type hints
    return db.query(User).filter_by(id=user_id).first()
\`\`\`

### Enforcement
This rule is checked by: @Backend, @Architect

### Exceptions
Document any valid exceptions to this rule.
```

### Severity Levels

Use these severity markers in your rule titles:

- **BLOCKER** - Must fix, build will fail
- **ERROR** - Should fix, may cause issues
- **WARNING** - Should review, best practice
- **INFO** - Informational, suggestion

### Example: Creating a Performance Rule

```bash
# Create new rule file
cat > .agent/rules/performance.mdc << 'EOF'
# Performance Standards

## BLOCKER: No Blocking Operations in Async Functions

Blocking operations in async functions defeat the purpose of async/await
and can cause severe performance degradation.

### Examples

**✅ Good:**
\`\`\`python
async def fetch_user_data(user_id: str) -> dict:
    # Non-blocking database query
    user = await db.execute(select(User).where(User.id == user_id))
    return user.to_dict()
\`\`\`

**❌ Bad:**
\`\`\`python
async def fetch_user_data(user_id: str) -> dict:
    # Blocking call in async function!
    user = db.query(User).filter_by(id=user_id).first()
    return user.to_dict()
\`\`\`

### Enforcement
This rule is checked by: @Backend, @Architect

## WARNING: Database Query Optimization

All frequently-used queries should have appropriate indexes.

### Checklist
- [ ] Queries measured in production or load tests
- [ ] Indexes created for WHERE clauses
- [ ] N+1 queries avoided (use eager loading)
- [ ] Query plan analyzed with EXPLAIN

### Enforcement
This rule is checked by: @Backend, @Observability

## INFO: Caching Strategy

Consider caching for:
- Expensive computations
- External API calls
- Frequently accessed, rarely changed data

### Recommended Tools
- Redis for distributed caching
- LRU cache for in-memory caching
- HTTP caching headers for API responses
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
- .agent/rules/performance.mdc
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

**In rule file** (`.agent/rules/security.mdc`):

```markdown
## BLOCKER: No Secrets in Code

See: .agent/instructions/security/secrets-management.md
```

**In instruction file** (`.agent/instructions/security/secrets-management.md`):

```markdown
# Secrets Management

This enforces the rule: .agent/rules/security.mdc → "No Secrets in Code"

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
## BLOCKER: Functions Must Have Type Hints

All public functions must have type hints for parameters and return values.

**Good:**
\`\`\`python
def calculate_total(items: List[Item]) -> Decimal:
    return sum(item.price for item in items)
\`\`\`

**Bad:**
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
## BLOCKER: Validate All User Input

Added after: SEC-2026-001 (SQL Injection vulnerability)

All user-provided data must be validated before processing.
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
