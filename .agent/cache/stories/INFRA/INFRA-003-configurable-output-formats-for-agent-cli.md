# INFRA-003: Configurable Output Formats for Agent CLI

## State
INFRA-003-003-003-003-003-003-003-003-003-003-003-003-003-003-003-003-003-003

## Problem Statement
Currently, the `agent` CLI outputs data in a "pretty print" format using Rich tables, which is excellent for human readability but problematic for:
- **Programmatic consumption**: Scripts and CI/CD pipelines need machine-readable formats (JSON, CSV)
- **Data export**: Users want to export story/plan/runbook lists to spreadsheets or databases
- **Tool integration**: Piping output to tools like `jq`, `awk`, or `grep` requires structured or plain-text formats
- **Documentation**: Generating reports or embedding output in markdown documentation

## User Story
As a **developer or automation engineer**, I want to **specify the output format for agent commands** (e.g., `agent list stories --format json --output stories.json`), so that I can **programmatically process, export, and integrate agent data into my workflows and tools**.

## Acceptance Criteria
- [ ] **AC1**: Given I run `agent list stories --format json`, When the command executes, Then output is valid JSON with all story data (ID, Title, State, Path).
- [ ] **AC2**: Given I run `agent list plans --format csv`, When the command executes, Then output is valid CSV with headers and proper escaping.
- [ ] **AC3**: Given I run `agent list runbooks --format yaml`, When the command executes, Then output is valid YAML with proper structure.
- [ ] **AC4**: Given I run `agent list stories --format markdown`, When the command executes, Then output is a properly formatted Markdown table.
- [ ] **AC5**: Given I run `agent list stories --format plain`, When the command executes, Then output is plain text with tab-separated or space-aligned columns.
- [ ] **AC6**: Given I run `agent list stories` without `--format`, When the command executes, Then output defaults to the current Rich pretty-print format (backward compatibility).
- [ ] **AC7**: Given I specify an invalid format, When the command runs, Then it shows a clear error message listing valid formats.
- [ ] **AC8**: The `--format` flag is consistently available across all relevant commands (`list stories`, `list plans`, `list runbooks`, `check`, `preflight`).
- [ ] **AC9**: Given I run `agent list stories --format json --output stories.json`, When the command executes, Then the output is written to `stories.json` instead of stdout.
- [ ] **AC10**: Given I run `agent list stories --format csv -o results.csv`, When the command executes, Then the output is written to `results.csv` (short flag works).
- [ ] **AC11**: Given I specify `--output path/to/file.json` with a non-existent directory, When the command runs, Then it creates the parent directories automatically.
- [ ] **AC12**: Given I specify `--output existing-file.json` and the file exists, When the command runs, Then it overwrites the file without prompting (standard Unix behavior).
- [ ] **AC13**: Given I run `--output` without `--format`, When the command executes, Then it uses the default format (pretty) but writes to file.
- [ ] **Negative Test**: System handles empty result sets gracefully in all formats (e.g., `[]` for JSON, empty CSV with headers).
- [ ] **Negative Test**: Given I specify `--output /invalid/path/file.json` with insufficient permissions, When the command runs, Then it shows a clear error message about write permissions.

## Supported Formats
- **pretty** (default): Rich tables with colors and formatting
- **json**: Machine-readable JSON array of objects
- **csv**: Comma-separated values with headers
- **yaml**: YAML array/list format
- **markdown**: GitHub-flavored Markdown tables
- **plain**: Tab-separated or space-aligned plain text
- **tsv**: Tab-separated values (alternative to CSV)

## Non-Functional Requirements
- **Performance**: Format conversion should add <10ms overhead for typical result sets (<100 items)
- **Security**: Ensure proper escaping for CSV/TSV to prevent injection attacks
- **Compliance**: PII scrubbing must work across all output formats
- **Observability**: Log which format was requested for analytics

## Linked ADRs
- (No ADR required for this change, but should follow existing CLI patterns)

## Impact Analysis Summary
**Components touched:**
- `.agent/src/agent/commands/list.py` (primary changes)
- `.agent/src/agent/commands/check.py` (if outputting structured data)
- `.agent/src/agent/core/` (new `formatters.py` module for format conversion logic)
- Tests: `tests/commands/test_list.py`, new `tests/core/test_formatters.py`

**Workflows affected:**
- CI/CD pipelines that parse `agent` output
- Documentation generation scripts
- Developer workflows using `agent list` for validation

**Risks identified:**
- **Breaking change risk**: Low (adding optional flag, default behavior unchanged)
- **CSV injection**: Medium (must sanitize data for CSV/TSV output)
- **Performance**: Low (formatting is fast for typical data volumes)

## Test Strategy
**Unit Tests:**
- Test each formatter function (JSON, CSV, YAML, Markdown, plain) with sample data
- Test empty result sets in all formats
- Test special characters and escaping (CSV injection, markdown characters)

**Integration Tests:**
- Test `agent list stories --format <each-format>` end-to-end
- Verify output can be parsed by standard tools (`jq` for JSON, spreadsheet import for CSV)
- Test filtering combined with formatting (e.g., `--format json --plan PLAN-001`)

**Validation:**
- JSON output validated with `jq .`
- CSV output imported into Excel/Google Sheets
- YAML output validated with `yamllint`
- Markdown rendered in GitHub preview

## Rollback Plan
- If issues arise, the `--format` flag can be hidden/disabled via feature flag
- Default behavior (Rich tables) remains unchanged, so users unaffected
- Revert specific formatter implementation if bugs found in one format
