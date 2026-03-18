This decomposition breaks **INFRA-158** into three focused stories. This separation ensures that logic for parsing and file resolution is decoupled from the I/O-heavy story file manipulation and the CLI command orchestration.

## Plan

1.  **INFRA-158.1: Implement Reference Extraction and Metadata Resolution**
    *   Focus on regex extraction and looking up titles from ADR/Journey files.
    *   Target: `agent/commands/utils.py`.
2.  **INFRA-158.2: Implement Atomic Story File Merging**
    *   Focus on the markdown manipulation logic to update specific sections in-place.
    *   Target: `agent/commands/utils.py`.
3.  **INFRA-158.3: Orchestrate Back-Population in `new-runbook`**
    *   Focus on connecting the utilities to the command flow and adding structured logging.
    *   Target: `agent/commands/runbook.py`.

---

## INFRA-158.1: Implement Reference Extraction and Metadata Resolution

**Description:**
Implement the core logic to identify ADR and Journey IDs within a text block and resolve them to their descriptive names by checking the local filesystem.

**Acceptance Criteria:**
- [ ] Implement `extract_adr_refs(text: str) -> List[str]` using regex `ADR-\d+`.
- [ ] Implement `extract_journey_refs(text: str) -> List[str]` using regex `JRN-\d+`.
- [ ] Implement `resolve_adr_title(adr_id: str) -> Optional[str]`:
    - Searches `.agent/docs/adrs/` for a file matching `{adr_id}*.md`.
    - Returns the first H1 or the filename suffix if found.
- [ ] Implement `resolve_journey_name(jrn_id: str) -> Optional[str]`:
    - Searches for the journey YAML file.
    - Parses YAML to extract the `name` field.
- [ ] Returns `None` if files are missing or unreadable.

**Technical Notes:**
- Add to `agent/commands/utils.py`.
- Must handle deduplication of IDs before resolution.
- Performance: File lookups must use `pathlib` and globbing.

---

## INFRA-158.2: Implement Atomic Story File Merging

**Description:**
Develop the utility to update a story markdown file's "Linked" sections without corrupting the rest of the file or creating duplicates.

**Acceptance Criteria:**
- [ ] Implement `merge_story_links(story_path: Path, adrs: List[Tuple[id, title]], journeys: List[Tuple[id, title]])`.
- [ ] **Idempotency**: If `ADR-001` is already in the file, it is not added again.
- [ ] **Section Logic**: Replaces `- None` with the new list of links or appends to the existing list.
- [ ] **Atomicity**: Writes the updated content to a temporary file in the same directory, then uses `os.replace()` to overwrite the original.
- [ ] **Negative Path**: If the story file is missing or `PermissionError` occurs, raise a specific `StoryUpdateError` for the caller to handle.

**Technical Notes:**
- Use regex or a simple line-by-line parser to identify the `## Linked ADRs` and `## Linked Journeys` blocks.
- Ensure formatting (newlines and indentation) matches the existing project style.

---

## INFRA-158.3: Orchestrate Back-Population in `new-runbook`

**Description:**
Integrate the extraction and merging utilities into the `agent new-runbook` command flow and add observability.

**Acceptance Criteria:**
- [ ] Call extraction and merging logic in `agent/commands/runbook.py` immediately after the runbook file is successfully written.
- [ ] **Best-Effort Execution**: Wrap the back-population in a try/except block. If it fails (e.g., `StoryUpdateError`), log a warning but exit the command with code `0`.
- [ ] **Observability**: Emit a structured log event `story_links_updated` with `extra={ "story_id": ..., "adrs_added": [...], "journeys_added": [...] }`.
- [ ] **No-op Check**: If no new references are found compared to what is already in the story, do not attempt to write the file and do not emit the log event.

**Technical Notes:**
- Ensure the `story_id` is extracted from the filepath or the file content for the log event.
- Follow existing patterns in `runbook.py` for accessing `agent_config` to locate ADR/Journey directories.