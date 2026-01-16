# INFRA-011: Improve Impact Analysis

## Parent Plan
INFRA-008

## State
COMMITTED

## Problem Statement
The `agent impact` command's static analysis is very limited (only lists files). It prints "TBD" for workflows and risks. We can do better by parsing imports to identify reverse dependencies.

**Current Limitations:**
- No dependency graph analysis
- Cannot identify which files will be affected by changes
- Reviewers must manually trace imports to assess risk
- Static analysis provides minimal value compared to AI mode

**Desired State:**
- Automatic reverse dependency detection
- Show which files import the changed files
- Help reviewers understand blast radius without AI
- Fast performance even on large repositories

## User Story
As a reviewer, I want `agent impact` to tell me which other files depend on the changed files, so I can assess risk even without AI.

## Acceptance Criteria
- [ ] Static analysis parses Python `import` statements using AST (not regex)
- [ ] Static analysis parses JS `import/require` statements using regex
- [ ] Module names are resolved to actual file paths (e.g., `agent.core.utils` → `.agent/src/agent/core/utils.py`)
- [ ] Identifies files that import the changed files (reverse dependency lookup)
- [ ] Updates the "Impact Analysis Summary" to list these dependent components
- [ ] Performance: Analysis completes in <5 seconds for repos with 500 files
- [ ] Handles edge cases: circular imports, multi-line imports, malformed files

## Technical Requirements

### Python Import Parsing
- **Use AST parsing** (not string matching) via `ast.parse()`
- Handle all import patterns:
  - `import x`
  - `from x import y`
  - `from x import y, z`
  - `import x as y`
  - Multi-line imports
- Resolve module names to file paths:
  - `agent.core.utils` → `.agent/src/agent/core/utils.py`
  - `agent.core` → `.agent/src/agent/core/__init__.py`

### JavaScript Import Parsing
- Use regex patterns (AST parsing too complex for JS/TS)
- Handle ES6 imports: `import x from './path'`
- Handle CommonJS: `require('./path')`
- Resolve relative imports: `'./utils'` → `same_dir/utils.js`
- Try common extensions: `.js`, `.ts`, `.tsx`, `.jsx`
- Handle index files: `'./dir'` → `dir/index.ts`

### Performance Optimization
- Cache parsed dependencies with `@lru_cache(maxsize=1000)`
- Log warnings if analysis takes >5 seconds
- Skip unparsable files gracefully

### Error Handling
- Handle syntax errors in Python files
- Handle encoding errors (non-UTF8 files)
- Skip binary files
- Provide actionable error messages

## Impact Analysis Summary
Components touched: `agent/commands/check.py`, `agent/core/dependency_analyzer.py` (new)
Workflows affected: Preflight, Review.
Risks identified: Parsing might be slow on large repos (mitigated with caching).

## Test Strategy
- **Unit Tests:**
  - Test Python AST parsing with various import styles
  - Test JavaScript regex parsing with ES6 and CommonJS
  - Test module-to-file path resolution
  - Test reverse dependency resolution
  - Test caching behavior
  
- **Integration Tests:**
  - Create file A and file B (where B imports A)
  - Modify A
  - Run `agent impact`
  - Verify B is listed as impacted
  
- **Performance Tests:**
  - Benchmark on repos with 50, 500, and 1000 files
  - Verify <5 second completion time

## Implementation Notes

### Key Design Decisions
1. **AST for Python**: More reliable than regex, handles all edge cases
2. **Regex for JavaScript**: Simpler than full AST parsing, sufficient for common patterns
3. **Caching**: Essential for performance on large repos
4. **Graceful degradation**: Skip unparsable files rather than failing

### Files to Create/Modify
- **NEW**: `.agent/src/agent/core/dependency_analyzer.py` - Core analysis logic
- **MODIFY**: `.agent/src/agent/commands/check.py` - Integrate into `impact()` command
- **MODIFY**: `.agent/src/agent/core/utils.py` - Add file validation helpers

### Integration Points
- `impact()` function in `check.py` (around line 288)
- Get changed files from `git diff --cached`
- Display results with rich formatting
- Support `--update-story` flag to write analysis to story file

