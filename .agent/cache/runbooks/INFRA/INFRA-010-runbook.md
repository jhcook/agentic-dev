# STORY-ID: INFRA-010: Enhance Implement Command

Status: ACCEPTED

## Goal Description
Enhance the functionality of the `env -u VIRTUAL_ENV uv run agent implement` command to include an `--apply` flag. When used, this flag should allow developers to automatically apply changes to the file system based on the code snippets provided in the runbook, while ensuring necessary safeguards such as confirmations to prevent accidental overwrites.

---

## Panel Review Findings

### **@Architect**
- Expanding this capability aligns well with the goal of increasing system "agency" and reducing manual operations for developers.
- There is a risk of applying erroneous or incomplete changes if the AI's code responses are not rigorously validated, warranting a fallback system.
- Handling edge cases (e.g., malformed runbooks, partial code blocks, and large repositories) needs careful consideration.

### **@Security**
- Automating file changes introduces significant risks if safeguards, such as the confirmation step or input validation, are not implemented robustly.
- The `--apply` flag should log every file updated and provide a diff view for developers to review changes before confirmation.
- The system must ensure no malicious code is inadvertently executed or injected into critical project files.
- Review permissions required when writing to specific directories or modifying shared libraries.

### **@QA**
- The feature requires rigorous testing, including:
  - Scenarios where the runbook contains invalid or unparseable content.
  - Concurrent usage of the `--apply` option with other commands (e.g., `--yes`).
  - Stress-testing large repositories and nested file structures for performance.
- Edge cases where code conflicts and merge issues arise should also be explored.

### **@Docs**
- Documentation updates are critical to guide users on using the `--apply` flag safely and effectively.
- Detailed explanation required for:
  - Differences between `--apply` and normal operation.
  - Configurations for disabling or warning when the operation is unsafe.
  - Explanation of backup/undo mechanisms for applied files.

### **@Compliance**
- Since this functionality modifies files programmatically, ensure adherence to **Immutability of Logic (adr-standards.mdc)** by documenting decisions about implementation safeguards in ADRs.
- Validate the feature for compliance with security policies, ensuring no unintended manipulation of sensitive data or credentials in the repository.

### **@Observability**
- Clear observability is critical for debugging and auditing automated file changes:
  - Logs must capture every action, including before/after file states, skipped files, and the reason for skips.
  - Implement metrics for success, failed attempts, and applied changes to help monitor feature usage and error trends.
- No sensitive information (e.g., credentials, API keys) should appear in logs.

---

## Implementation Steps

### Step 1: Extend Command Parsing
#### MODIFY `agent/commands/implement.py`
- Add `--apply` and `--yes` flags supported by the command:
```python
@click.option('--apply', is_flag=True, default=False, help="Apply changes based on the runbook.")
@click.option('--yes', is_flag=True, default=False, help="Skip confirmation prompts.")
```

### Step 2: Parse the Runbook for Code Blocks
#### NEW `agent/utils/code_parser.py`
- Implement a utility function to extract and validate code blocks from the runbook:
```python
def parse_code_blocks(runbook: str) -> List[dict]:
    """
    Parses the runbook text for actionable code blocks.

    Args:
        runbook (str): The text of the runbook.
    
    Returns:
        List[dict]: A list of dictionaries with 'file', 'line', and 'content' keys.
    """
    # Pseudocode for Markdown code block extraction
    code_blocks = []
    for match in re.finditer(r"```(.*?)```", runbook, re.DOTALL):
        block = match.group(1)
        file_path, line_no, content = extract_details_from_block(block)
        if validate_code_snippet(content):
            code_blocks.append({'file': file_path, 'line': line_no, 'content': content})
    return code_blocks
```

### Step 3: Apply Changes to Files
#### MODIFY `agent/commands/implement.py`
- Process parsed code blocks and apply them to the file system.
- Add a confirmation prompt logic, which auto-approves changes when `--yes` is used:
```python
if apply:
    changes = parse_code_blocks(runbook)
    for change in changes:
        if not yes:
            confirm = input(f"Apply change to {change['file']}? (y/n): ")
            if confirm.lower() != 'y':
                continue
        apply_change_to_file(change['file'], change['line'], change['content'])
```

### Step 4: Add Logging and Backup Mechanism
#### MODIFY `agent/utils/logger.py`
- Enhance existing logging to include applied changes for auditing.
#### NEW `agent/utils/backup_manager.py`
- Create a module for backing up files before modification:
```python
def backup_file(file_path: str):
    backup_path = f"{file_path}.backup-{datetime.now().timestamp()}"
    shutil.copy(file_path, backup_path)
```

### Step 5: Testing & Validation
#### Add Unit Tests in `tests/agent/test_implement.py`
- Test cases:
  - Valid runbook application generates correct file changes.
  - Invalid runbook raises appropriate errors.
  - Confirmation bypass works correctly with `--yes`.
  - Files are not overwritten unnecessarily when users skip changes.

---

## Verification Plan

### Automated Tests
- [ ] Test for valid runbooks applying changes correctly.
- [ ] Test for invalid runbooks triggering errors.
- [ ] Test for confirmation behaviors (yes, no, skip).
- [ ] Test backup file creation and restoration.
- [ ] Test impact on large codebases (>100 files).

### Manual Verification
1. Create test repositories with dummy files.
2. Run `env -u VIRTUAL_ENV uv run agent implement <RUNBOOK_ID> --apply`.
3. Confirm file changes visually.
4. Validate backup files are created and reversible.

---

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with new feature details.
- [ ] README.md updated with usage instructions for `--apply` flag.
- [ ] ADR for safeguard decisions updated (e.g., confirmation, backup).

### Observability
- [ ] Logging implemented to track file modifications (paths, content changed).
- [ ] Alerts for errors and non-standard `--apply` behaviors.
- [ ] Metrics on usage frequency and error rate.

### Testing
- [ ] All unit and integration tests passed.
- [ ] Stress testing completed for edge cases.
- [ ] Compatibility with other commands verified.

---