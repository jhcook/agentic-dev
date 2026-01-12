# Troubleshooting Guide

Common issues and their solutions.

## Installation Issues

### "Command not found: agent"

**Problem:** Shell can't find the agent executable.

**Solutions:**

1. **Use full path:**
   ```bash
   /path/to/repo/.agent/bin/agent --version
   ```

2. **Add to PATH:**
   ```bash
   export PATH="$PATH:$(pwd)/.agent/bin"
   agent --version
   ```

3. **Make permanent:**
   ```bash
   echo 'export PATH="$PATH:/Users/jcook/repo/agentic-dev/.agent/bin"' >> ~/.zshrc
   source ~/.zshrc
   ```

### "No module named 'agent'"

**Problem:** Python can't find the agent module.

**Solution:**
```bash
# Install the agent package
pip install -e .agent/

# Set PYTHONPATH
export PYTHONPATH=.agent/src
agent --version
```

### "Permission denied: .agent/bin/agent"

**Problem:** Execute permission not set.

**Solution:**
```bash
chmod +x .agent/bin/agent
```

## Command Errors

### "Story file not found for STORY-ID"

**Problem:** Story doesn't exist or wrong ID.

**Solutions:**

1. **List all stories:**
   ```bash
   agent list-stories
   ```

2. **Check ID format:**
   ```
   ✅ WEB-001
   ❌ web-001
   ❌ WEB001
   ❌ WEB-1 (should be WEB-001)
   ```

3. **Verify file exists:**
   ```bash
   ls .agent/cache/stories/WEB/
   ```

### "Story must be in COMMITTED state"

**Problem:** Trying to generate runbook for non-committed story.

**Solution:**
```bash
# Edit story
vim .agent/cache/stories/WEB/WEB-001-feature.md

# Change state:
## State
COMMITTED

# Now generate runbook
agent new-runbook WEB-001
```

### "Runbook must be in ACCEPTED state"

**Problem:** Trying to implement non-accepted runbook.

**Solution:**
```bash
# Edit runbook
vim .agent/cache/runbooks/WEB/WEB-001-runbook.md

# Change status:
Status: ACCEPTED

# Now implement
agent implement WEB-001
```

### "Failed to create PR: No commits"

**Problem:** Current branch has no commits vs. base branch.

**Solutions:**

1. **Commit your changes first:**
   ```bash
   git add .
   agent commit --story WEB-001
   ```

2. **Check branch:**
   ```bash
   git log origin/main..HEAD
   # Should show commits
   ```

## AI Issues

### "AI returned empty response"

**Problem:** AI provider not responding.

**Debugging:**

1. **Check API key:**
   ```bash
   echo $GEMINI_API_KEY
   echo $OPENAI_API_KEY
   ```

2. **Test API directly:**
   ```bash
   # Gemini
   curl -H "Content-Type: application/json" \
     -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
     "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key=$GEMINI_API_KEY"
   ```

3. **Try different provider:**
   ```bash
   agent --provider openai new-runbook WEB-001
   agent --provider gh new-runbook WEB-001
   ```

4. **Check logs:**
   ```bash
   # Enable debug logging
   export AGENT_LOG_LEVEL=DEBUG
   agent new-runbook WEB-001
   ```

### "Context window exceeded"

**Problem:** Input too large for model's context window.

**Solutions:**

1. **Use larger context model (Gemini):**
   ```bash
   agent --provider gemini new-runbook WEB-001
   ```

2. **Reduce chunk size:**
   ```bash
   export AGENT_CHUNK_SIZE=3000
   agent preflight --story WEB-001 --ai
   ```

3. **Simplify story:**
   - Remove verbose problem statement
   - Condense acceptance criteria
   - Remove redundant sections

### "Rate limit exceeded"

**Problem:** Too many API requests in short time.

**Solutions:**

1. **Wait and retry:**
   ```bash
   sleep 60
   agent new-runbook WEB-001
   ```

2. **Use different provider:**
   ```bash
   agent --provider openai new-runbook WEB-001
   ```

3. **Upgrade API tier:**
   - Gemini: Free → Paid
   - OpenAI: Increase usage tier

### "API key invalid"

**Problem:** API key expired or incorrect.

**Solutions:**

1. **Regenerate key:**
   - Gemini: [AI Studio](https://makersuite.google.com/app/apikey)
   - OpenAI: [Platform](https://platform.openai.com/api-keys)

2. **Update environment:**
   ```bash
   export GEMINI_API_KEY="new-key-here"
   ```

3. **Check for typos:**
   ```bash
   # Keys should look like:
   # Gemini: AIza...
   # OpenAI: sk-...
   ```

## Preflight Issues

### "Preflight failed: Linting errors"

**Problem:** Code doesn't pass linter.

**Solutions:**

1. **Run linter directly:**
   ```bash
   # Python
   flake8 src/
   
   # JavaScript
   eslint src/
   ```

2. **Auto-fix:**
   ```bash
   # Python
   black src/
   
   # JavaScript
   eslint --fix src/
   ```

3. **Review errors:**
   Check the preflight output for specific line numbers and issues.

### "Preflight failed: Tests failing"

**Problem:** Test suite has failures.

**Solutions:**

1. **Run tests directly:**
   ```bash
   pytest tests/
   # or
   npm test
   ```

2. **Fix failing tests:**
   Review test output and fix broken functionality.

3. **Update tests:**
   If requirements changed, update test expectations.

### "Preflight failed: @Security blocker"

**Common issues:**

**1. Hardcoded secrets:**
```python
# ❌ Bad
API_KEY = "sk-1234567890..."

# ✅ Good
API_KEY = os.environ.get('API_KEY')
```

**2. PII in logs:**
```python
# ❌ Bad
logger.info(f"User {user.email} logged in")

# ✅ Good  
logger.info(f"User {user.id} logged in")
```

**3. SQL injection:**
```python
# ❌ Bad
db.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ Good
db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### "Preflight failed: @Docs blocker"

**Common issues:**

**1. Missing CHANGELOG:**
```bash
# Add entry to CHANGELOG.md
vim CHANGELOG.md
```

```markdown
## [Unreleased]

### Added
- New user profile page [WEB-001]
```

**2. Missing API documentation:**
```bash
# Update OpenAPI spec
vim docs/openapi.yaml
```

**3. Missing docstrings:**
```python
# ❌ Bad
def calculate_total(items):
    return sum(item.price for item in items)

# ✅ Good
def calculate_total(items: List[Item]) -> Decimal:
    """Calculate total price of items.
    
    Args:
        items: List of items to sum
        
    Returns:
        Total price as Decimal
    """
    return sum(item.price for item in items)
```

### "Preflight failed: @QA blocker"

**Common issues:**

**1. No tests for new feature:**
```bash
# Add tests
vim tests/test_feature.py
```

**2. Test coverage too low:**
```bash
# Check coverage
pytest --cov=src tests/

# Add tests for uncovered code
```

**3. No test strategy in story:**
```markdown
## Test Strategy
- Unit tests: test_feature.py
- Integration tests: test_api.py  
- E2E tests: Using Playwright
```

## Workflow Issues

### "Can't create story: Plan not approved"

**Problem:** Parent plan is not in APPROVED state.

**Solution:**
```bash
# Find plan
agent list-plans

# Update plan status
vim .agent/cache/plans/WEB/WEB-PLAN-001.md

# Change:
Status: APPROVED
```

### "Can't generate runbook: Story not committed"

**Problem:** Story state is DRAFT or OPEN.

**Solution:**
```bash
# Update story
vim .agent/cache/stories/WEB/WEB-001-feature.md

# Change:
## State
COMMITTED
```

### "Can't implement: Runbook not accepted"

**Problem:** Runbook status is PROPOSED.

**Solution:**
```bash
# Review runbook
vim .agent/cache/runbooks/WEB/WEB-001-runbook.md

# After review, change:
Status: ACCEPTED
```

## Git Issues

### "Cannot create PR: Branch is main"

**Problem:** Trying to create PR from main branch.

**Solution:**
```bash
# Create feature branch
git checkout -b feature/WEB-001-user-profile

# Make changes
# Commit
agent commit --story WEB-001

# Now create PR
agent pr --story WEB-001
```

### "Cannot commit: Nothing staged"

**Problem:** No files added to staging area.

**Solution:**
```bash
# Stage files
git add .

# Or specific files
git add src/feature.ts tests/feature.test.ts

# Now commit
agent commit --story WEB-001
```

### "Merge conflict in story file"

**Problem:** Multiple people edited same story.

**Solution:**
```bash
# Pull latest
git pull origin main

# Resolve conflicts in story file
vim .agent/cache/stories/WEB/WEB-001-feature.md

# Keep both changes if possible
git add .agent/cache/stories/WEB/WEB-001-feature.md
git commit -m "Merge story changes"
```

## Performance Issues

### "Preflight takes too long"

**Problem:** AI governance review is slow.

**Solutions:**

1. **Skip AI for quick checks:**
   ```bash
   # Basic checks only (fast)
   agent preflight --story WEB-001
   ```

2. **Reduce number of roles:**
   ```yaml
   # Edit .agent/etc/agents.yaml
   team:
     - role: security  # Keep critical
     - role: qa        # Keep critical
     # Comment out others for speed
   ```

3. **Use faster model:**
   ```bash
   agent --provider gemini preflight --story WEB-001 --ai
   ```

### "Runbook generation is slow"

**Problem:** Large story or rules.

**Solutions:**

1. **Simplify story:**
   - Remove verbose sections
   - Focus on essentials

2. **Reduce rules:**
   ```bash
   # Temporarily move non-critical rules
   mkdir .agent/rules/temp
   mv .agent/rules/detailed-*.mdc .agent/rules/temp/
   ```

3. **Use faster model:**
   Configure in `.agent/etc/router.yaml`

## Debugging Tools

### Enable Debug Logging

```bash
export AGENT_LOG_LEVEL=DEBUG
agent new-runbook WEB-001 2>&1 | tee debug.log
```

### Inspect AI Prompts

```python
# Edit .agent/src/agent/core/ai.py

def complete(self, system: str, user: str) -> str:
    # Add debugging
    print("=" * 80)
    print("SYSTEM PROMPT:")
    print(system)
    print("=" * 80)
    print("USER PROMPT:")
    print(user)
    print("=" * 80)
    
    # ... existing code
```

### Check Configuration

```bash
# Verify config files
cat .agent/etc/agents.yaml
cat .agent/etc/router.yaml

# Check environment
env | grep -E 'GEMINI|OPENAI|AGENT'
```

### Validate Story/Runbook Format

```bash
# Use validation
agent validate-story WEB-001

# Manual check
cat .agent/cache/stories/WEB/WEB-001-feature.md | grep "## State"
cat .agent/cache/runbooks/WEB/WEB-001-runbook.md | grep "Status:"
```

## Getting Help

### Check Logs

```bash
# Preflight logs
cat .agent/logs/preflight-*.log | tail -100

# System logs
tail -f /var/log/agent.log  # If configured
```

### Community Support

1. **GitHub Issues:** Report bugs or feature requests
2. **GitHub Discussions:** Ask questions
3. **Documentation:** Check other docs in `/docs`

### Debugging Checklist

Before asking for help, verify:

- [ ] Latest version: `agent --version`
- [ ] Dependencies installed: `pip list`
- [ ] API keys set: `echo $GEMINI_API_KEY`
- [ ] Story/runbook states correct
- [ ] Git status clean: `git status`
- [ ] Logs reviewed: `cat .agent/logs/preflight-*.log`

---

**Related Documentation:**
- [Getting Started](getting_started.md)
- [Commands Reference](commands.md)
- [Configuration](configuration.md)
- [AI Integration](ai_integration.md)
