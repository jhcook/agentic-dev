# INFRA-074: Implement Oracle Preflight Pattern for All Providers

## State

COMMITTED

## Goal Description

Implement the "Oracle" preflight pattern for all providers to eliminate preflight hallucinations by using dynamic tool-driven retrieval instead of static context stuffing. This includes reducing diff context, enforcing role isolation, mandating tool-driven citations, and providing a NotebookLM MCP integration with local vector database fallback.

## Linked Journeys

- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

**@Architect**:

- The proposal aligns with the architectural goal of reducing context stuffing and improving agent reliability.
- The use of a local vector database is a sound approach for offline support and MCP fallback.
- ADRs might be needed to document the Oracle Pattern itself and the choice of local vector DB (e.g., LanceDB vs. ChromaDB).
- **Action**: Create ADRs for the Oracle Pattern and the Local Vector DB implementation choice.

**@Qa**:

- The acceptance criteria are well-defined and testable.
- E2E tests need to be created to verify the correct behavior across different providers and with/without NotebookLM MCP.
- The existing user flow `JRN-062` needs to be updated to reflect the changes.
- **Action**: Create E2E tests for each acceptance criterion and update existing user flow.

**@Security**:

- Ensure that the local vector database does not store any secrets or PII.
- Verify that the NotebookLM MCP integration is secure and does not expose any vulnerabilities.
- Implement proper input validation to prevent injection attacks when querying the vector database.
- The changes reduce reliance on context stuffing, which is a good move for security, but we need to ensure the vector database retrieval doesn't open new attack vectors.
- **Action**: Review the vector database implementation for security vulnerabilities and ensure no secrets or PII are stored.

**@Product**:

- The user story clearly defines the problem and the proposed solution.
- The acceptance criteria are comprehensive and cover all aspects of the implementation.
- The `--legacy-context` flag is a good way to provide backward compatibility for users who prefer the old approach.
- Ensure the transition to the Oracle pattern is smooth and users are informed about the changes.
- **Action**: Communicate the changes to users and provide documentation on how to use the new Oracle pattern.

**@Observability**:

- Add OpenTelemetry tracing for the new flows, including the NotebookLM MCP integration and the local vector database queries.
- Ensure that logs are structured and free of PII.
- Monitor the performance of the Oracle pattern and compare it to the old context stuffing approach.
- **Action**: Add OpenTelemetry tracing and structured logging for the new flows.

**@Docs**:

- Update the documentation to reflect the new Oracle pattern and the `--legacy-context` flag.
- Document how to configure and use the NotebookLM MCP integration and the local vector database.
- Document the new output schema with explicit verifiable citations.
- **Action**: Update the documentation to reflect the new Oracle pattern.

**@Compliance**:

- Ensure that the NotebookLM MCP integration and the local vector database comply with GDPR and SOC2 requirements.
- Verify that the data stored in the vector database is encrypted and that access controls are in place.
- Ensure that users have the right to erasure for any data stored in the vector database.
- **Action**: Review the implementation for GDPR and SOC2 compliance.

**@Mobile**:

- Ensure that the local vector database works correctly on mobile devices and does not consume excessive resources.
- Verify that the offline support is seamless and that users can access ADRs and rules even without an internet connection.
- **Action**: Test the local vector database on mobile devices.

**@Web**:

- No changes are required for the web frontend.

**@Backend**:

- Ensure that the API documentation (OpenAPI) is updated to reflect any changes to the preflight endpoint.
- Verify that the types are strictly enforced for the new flows.
- **Action**: Update the API documentation and verify type enforcement.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert prints to logger in `agent/commands/check.py`
- [ ] Fix formatting in `agent/core/governance.py`
- [ ] Update user flow JRN-062 in `.agent/journeys/`

## Implementation Steps

### `agent/commands/check.py`

#### MODIFY `agent/commands/check.py`

- Reduce the diff generation context from `-U10` to `-U3` when the Oracle Pattern is active.
- Add a check for the `--legacy-context` flag and use the original context stuffing behavior if it is provided.
- Implement the Notion sync awareness check before starting the preflight.

```python
import subprocess

def check():
    # ... existing code ...
    use_legacy_context = config.get("legacy_context", False)  # Assuming config can read CLI flags

    diff_context = "-U10" if use_legacy_context else "-U3"

    # Notion sync check (AC-10)
    if not use_legacy_context:
        from agent.sync.notion import NotionSync
        notion_sync = NotionSync()
        notion_sync.ensure_synchronized()
        
        # NotebookLM Automated Sync (AC-12)
        from agent.sync.notebooklm import ensure_notebooklm_sync
        ensure_notebooklm_sync()

    # ... existing code for diff generation ...
    diff_process = subprocess.Popen(
        ["git", "diff", f"--unified={diff_context}", base_branch, "--", *changed_files],
        cwd=config.project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # ... existing code ...
```

### `agent/core/governance.py`

#### MODIFY `agent/core/governance.py`

- Modify the prompt format to force the agent to cite its tool usage.
- Implement the logic to drop findings without explicit tool-verified citations.
- Implement the NotebookLM MCP routing logic, falling back to the local vector database if MCP is unavailable.

```python
def convene_council_full(...):
    # ... existing code ...

    prompt = (
        "Output your analysis in this EXACT format:\n"
        "VERDICT: PASS or BLOCK\n"
        "FINDINGS:\n"
        "- [Finding] (Source: [Exact file path or ADR ID retrieved via tools])\n"
    )

    # ... agent execution ...

    # Post-processing to validate citations
    validated_findings = []
    for finding in extracted_findings: #Assuming extracted_findings is a list of strings
        if _validate_reference(finding): # Needs implementation to check for citation
            validated_findings.append(finding)
        else:
            log(f"Dropping finding due to missing citation: {finding}")

    # ... create final report with validated_findings ...

def _validate_reference(finding: str) -> bool:
    # Implement logic to check if the finding has a valid citation
    # This could involve regex matching or parsing the finding string
    citation_regex = r"\(Source: \[.+\]\)"
    return bool(re.search(citation_regex, finding))
```

### `agent/core/adk/agents.py`

#### MODIFY `agent/core/adk/agents.py`

- Scope agent system instructions to strictly forbid evaluating out-of-domain logic.

```python
def create_agent(role, agent_name):
    other_domains = ", ".join([r['name'] for r in roles if r['name'] != role.get('name', agent_name)])
    system_instruction = (
        f"You are the {role.get('name', agent_name)} on the AI Governance Council.\n"
        f"You must use your tools to search the codebase and read ADRs.\n"
        f"You are strictly forbidden from evaluating {other_domains}.\n"
    )
    # ... rest of the agent creation logic ...
```

### `agent/core/context.py`

#### MODIFY `agent/core/context.py`

- Modify context_loader to conditionally load <adrs>, <rules>, and global <instructions> based on the `--legacy-context` flag.
- Implement Local Vector DB integration using ChromaDB or LanceDB as a fallback when NotebookLM MCP is not available.

```python
class ContextLoader:
    def load_context(self, story_id: str, legacy_context: bool = False):
        # ... existing code ...
        if legacy_context:
            # Load ADRs, rules, and instructions as before
            adrs = self._load_adrs()
            rules = self._load_rules()
            instructions = self._load_instructions()
        else:
            adrs = []
            rules = []
            instructions = []

        # NotebookLM MCP / Local Vector DB integration
        if not legacy_context:
            try:
                from agent.core.mcp.client import MCPClient # needs implemented.
                mcp_client = MCPClient() # Instantiate with appropriate server configuration
                # Query MCP
                context = mcp_client.get_context(story_id) # Place holder for MCP Query

            except Exception as e:
                print(f"MCP Server not detected. Falling back to local Vector DB: {e}")
                # Load Local Vector DB and query it.
                import chromadb # or LanceDB
                # Embed ADRS, .mdc files and search for relevant context
                context = self._query_local_vector_db(story_id)

        return {
            "adrs": adrs,
            "rules": rules,
            "instructions": instructions,
            "diff": diff,
            "story": story_content,
            "context": context # New context variable from MCP / Vector DB
        }

    def _query_local_vector_db(self, query: str) -> str:
        # Implement vector DB query logic here using ChromaDB or LanceDB
        # Ensure ADRs and rules are indexed in the vector DB
        # Search for relevant context based on the query string
        # Return the relevant context as a string
        return "Relevant context from local vector DB" # Placeholder

```

### `agent/sync/notion.py`

#### MODIFY `agent/sync/notion.py`

- Add a method to ensure that Notion is synchronised before beginning a preflight when the oracle pattern is enabled.

```python
class NotionSync:
    def ensure_synchronized(self) -> None:
        # Implement the logic to validate the Notion sync state
        # This could involve checking the last sync timestamp or running the sync protocol
        # If the sync is not up-to-date, trigger the sync protocol
        # Raise an exception or return an error code if the sync fails
        print("Ensuring Notion is synchronised") # Placeholder
```

### NEW `agent/core/mcp/client.py`

- Implement MCP Client based on ADR-010.

### NEW `agent/sync/notebooklm.py`

- Create a module to ensure a NotebookLM notebook exists for the current repository and to iterate over `docs/adrs/` and `.agent/rules/`, calling MCP tools (`notebook_add_text` or `notebook_add_drive`) to synchronize local architectural context to Google NotebookLM.

### NEW `agent/db/journey_index.py`

- Create a new class to index the journeys into local vectorDB.

## Verification Plan

### Automated Tests

- [x] Test AC-1: `test_check_diff_context` - Checks that the diff context is reduced to `-U3` when the Oracle Pattern is active.
- [x] Test AC-2: `test_check_no_static_injection` - Checks that `<adrs>`, `<rules>`, and global `<instructions>` are not statically injected into the initial user prompt unless the `--legacy-context` flag is provided.
- [x] Test AC-3: `test_legacy_context` - Checks that legacy mode (`--legacy-context`) perfectly preserves the original "Context Stuffing" behavior.
- [x] Test AC-4: `test_agent_instruction_scope` - Checks that agent system instructions in `agent/core/adk/agents.py` are scoped to strictly forbid evaluating out-of-domain logic.
- [x] Test AC-5: `test_citation_requirement` - Checks that preflight output schema strictly requires explicit verifiable citations for all findings (`Source: [Exact file path or ADR ID]`), dropping any finding without one.
- [x] Test AC-6: `test_tool_accessibility` - Checks that existing `read_file`, `search_codebase`, and `read_adr` tools remain fully accessible and correctly bound to all agents.
- [x] Test AC-7: `test_local_vector_db` - Checks that a proof-of-concept Local Vector DB (e.g., ChromaDB/LanceDB) integration is provided to index and semantically search rules and ADRs completely locally.
- [x] Test AC-8: `test_tool_usage` - Checks that E2E preflight test confirms that agents still check relevant rules by successfully searching or reading ADRs on their own.
- [x] Test AC-9: `test_provider_compatibility` - Checks that the Oracle Pattern functions correctly and efficiently across all supported providers (e.g., `--provider anthropic`, `--provider vertex`, `--provider gemini`).
- [x] Test AC-10: `test_notion_sync_awareness` - Checks that before the Oracle preflight begins, it triggers a lightweight validation check against the Notion sync state.
- [x] Test AC-11: `test_notebooklm_routing` - Checks that when the NotebookLM Enterprise API MCP server is detected in the environment, retrieval queries route through the MCP server first, deferring to the Local Vector DB only as a fallback.
- [x] Test AC-12: `test_notebooklm_sync` - Checks that the framework actively manages a NotebookLM instance by creating it if missing and pushing local rules/ADRs.

### Manual Verification

- [ ] Step 1: Run `env -u VIRTUAL_ENV uv run agent preflight` on a test branch with a known architectural violation and verify that the agent correctly identifies the violation and cites the relevant ADR.
- [ ] Step 2: Run `env -u VIRTUAL_ENV uv run agent preflight --legacy-context` on the same test branch and verify that the agent identifies the same violation using the original context stuffing approach.
- [ ] Step 3: Disable the NotebookLM MCP server and run `env -u VIRTUAL_ENV uv run agent preflight` on the same test branch and verify that the agent correctly identifies the violation using the local vector database.
- [ ] Step 4: Test on different providers `--provider anthropic`, `--provider vertex`, `--provider gemini`.
- [ ] Step 5: Introduce a new ADR and run `env -u VIRTUAL_ENV uv run agent preflight` on a branch with code that violates it. Verify that the agent picks up the new ADR.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated (if applicable)
- [x] API Documentation updated (if applicable)

### Observability

- [x] Logs are structured and free of PII
- [x] Metrics added for new features

### Testing

- [x] Unit tests passed
- [x] Integration tests passed
