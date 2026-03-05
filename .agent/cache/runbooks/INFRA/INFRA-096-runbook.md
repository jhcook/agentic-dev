# INFRA-096: Safe Implementation Apply

## State

ACCEPTED

## Goal Description

Replace the destructive full-file overwrite in `apply_change_to_file()` with a diff-based search/replace apply strategy, inject source context into AI prompts so the AI can see what it's editing, and add a file-size guard that rejects full-file overwrites for existing files above a configurable threshold. This is **Layer 2b** of the INFRA-089 defence-in-depth strategy.

## Linked Journeys

- JRN-064 — Forecast-Gated Story Decomposition

## Panel Review Findings

### @Architect

- **ADR Compliance**: Follows ADR-005 (AI-Driven Governance Preflight). All changes are self-contained within `implement.py` — no new modules needed. The search/replace parsing is a parsing concern, not an architectural boundary change.
- **Design Scope**: Three surgical modifications to `implement.py`:
  1. New parser (`parse_search_replace_blocks`) alongside existing `parse_code_blocks` — dual-format support.
  2. Source context injection (`extract_modify_files` + `build_source_context`) — reads runbook `[MODIFY]` markers, loads file contents, truncates large files.
  3. Apply strategy refactor — `apply_change_to_file()` gains a size guard; new `apply_search_replace_to_file()` handles surgical edits.
- **Backward Compatibility**: Full-file output remains the path for new files (AC-7). Existing `parse_code_blocks()` is NOT modified. The `--legacy-apply` flag (AC-8) bypasses the size guard entirely, using `log_skip_audit` per SOC2.
- **Token Budget**: Source context injection adds file content to the prompt. The 300 LOC / head+tail 100 truncation (AC-3) caps this. For the chunked path, only files referenced in the current chunk's `[MODIFY]` markers are injected — not all files from the entire runbook — to stay within token budget.
- **Risk**: The full-context path (L867–918) sends the entire runbook in one call. Source context for ALL `[MODIFY]` files is injected at once. If there are 10+ files, this may exceed the context window. Mitigation: log a warning if total prompt exceeds 80% of estimated context window (~100k chars).

### @QA

- **Test Strategy**: The story defines 9 test categories. Recommend:
  - **Parser Tests**: Valid single block, valid multiple blocks per file, mixed new-file + search/replace, malformed (missing `===`, missing `>>>`).
  - **Apply Tests**: Exact match success, no match rejection (AC-6), multiple blocks applied in order, partial match (one succeeds, one fails → full rollback).
  - **Size Guard Tests**: File < 200 LOC + full-file → accepted. File ≥ 200 LOC + full-file → rejected. File ≥ 200 LOC + search/replace → accepted. File ≥ 200 LOC + full-file + `--legacy-apply` → accepted (audit logged).
  - **Source Context Tests**: File < 300 LOC → full content. File > 300 LOC → head/tail with omission marker. Non-existent file → skipped with warning.
  - **Integration**: Mock AI returning search/replace output, verify file content after apply.
- **Test Isolation**: All tests MUST mock `subprocess.run`, `ai_service.complete`, and use `tmp_path` fixtures.

### @Security

- **Prompt Injection**: The search/replace format introduces a new parsing surface. A malicious search block could contain `===` or `>>>` markers inside code content. Mitigation: the parser uses greedy-but-bounded matching and requires the exact `<<<SEARCH` / `===` / `>>>` sequence on its own lines.
- **Data Privacy**: Source context injection reads file contents and sends them to the AI provider. These are local repo files already part of the codebase — no PII risk beyond what already exists in the existing prompt. The `scrub_sensitive_data()` call is NOT applied to source context (it would corrupt code). This is acceptable because source context is code, not user data.
- **Audit Logging**: `--legacy-apply` usage MUST call `log_skip_audit("Safe apply bypass", story_id)` per SOC2. Apply decisions (mode, file, lines_changed) are logged structurally.
- **No Path Traversal**: Source context injection reads files via `resolve_path()` which already prevents path traversal. The `extract_modify_files()` function only extracts paths from the runbook — it does not follow symlinks or access files outside the repo.

### @Product

- **UX**: Clear console feedback for each apply decision:
  - Search/replace applied: `✅ Applied 3 search/replace block(s) to path/file.py`
  - Size guard rejection: `❌ Rejected full-file overwrite for path/file.py (245 LOC > 200 threshold). Use search/replace format or --legacy-apply.`
  - Match failure: `❌ Search block not found in path/file.py. No changes applied.`
  - Source context injected: `[dim]📄 Injected source context for 4 file(s) ({N} chars)[/dim]`
- **AC Mapping**:
  - AC-1 → Step 3 (search/replace parser) + Step 5 (system prompt)
  - AC-2 → Step 2 (source context injection)
  - AC-3 → Step 2 (truncation in `build_source_context`)
  - AC-4 → Step 4 (apply strategy detection)
  - AC-5 → Step 4 (file size guard)
  - AC-6 → Step 4 (match failure handling)
  - AC-7 → Step 4 (new file path unchanged)
  - AC-8 → Step 7 (`--legacy-apply` flag)

### @Observability

- **Structured Logging**: Log each apply decision with fields: `apply_mode` (search_replace | full_file | rejected), `file`, `lines_changed`, `file_loc`, `threshold`.
- **OpenTelemetry**: Add spans:
  - `implement.apply_change` — wraps each file apply operation with attributes: `apply_mode`, `file`, `success`.
  - `implement.parse_search_replace` — wraps parsing of AI output.
  - `implement.inject_source_context` — wraps context injection with attributes: `file_count`, `total_chars`.
- **Token Budget Warning**: Log a warning if total prompt exceeds 80% of estimated context window.

### @Docs

- **CHANGELOG**: Add INFRA-096 entry under "Added" section.
- **CLI Help**: Document `--legacy-apply` flag in the `implement` command help text.

### @Compliance

- **SOC2**: `--legacy-apply` flag triggers `log_skip_audit` — satisfies audit trail requirement. Apply mode decisions are logged with structured data.
- **Licensing**: New test file must include Apache 2.0 header.

### @Mobile

- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Web

- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Backend

- **Type Safety**: New functions use typed parameters and return types. `parse_search_replace_blocks` returns `List[Dict[str, str]]` consistent with `parse_code_blocks`.
- **Pattern**: Follow existing `parse_code_blocks` → `apply_change_to_file` flow. The new `parse_search_replace_blocks` sits alongside `parse_code_blocks` — both are called, results merged. `apply_search_replace_to_file` is a new function parallel to `apply_change_to_file`.
- **Error Handling**: Match failures in search/replace are non-fatal per-block but abort the entire file's changes (no partial apply). The file is left unchanged. This prevents the "half-applied search/replace" corruption scenario.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract the system prompt string literals into named constants or a dedicated prompt builder function to reduce the size of `implement()`.
- [ ] Add type annotation for `full_content` (currently untyped `str`).

## Implementation Steps

### Search/Replace Parser

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 1 — Module-level imports and constants for safe apply**

- Add the `defaultdict` import to the existing imports block (around line 21):

    ```python
    from collections import defaultdict
    ```

- Add the following constants after the existing circuit breaker constants (after line 48):

    ```python
    # Safe Apply Thresholds (INFRA-096)
    FILE_SIZE_GUARD_THRESHOLD = 200   # LOC — reject full-file overwrite above this
    SOURCE_CONTEXT_MAX_LOC = 300      # LOC — truncate source context above this
    SOURCE_CONTEXT_HEAD_TAIL = 100    # LOC — lines to keep from head/tail when truncating
    ```

**Step 2 — Add `parse_search_replace_blocks()` function**

- Add a new function after `parse_code_blocks()` (after line 89):

    ```python
    def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]:
        """
        Parse search/replace blocks from AI-generated content.

        Expected format (per file):
            File: path/to/file.py
            <<<SEARCH
            exact lines to find
            ===
            replacement lines
            >>>

        Multiple blocks per file are supported.

        Returns:
            List of dicts with 'file', 'search', 'replace' keys.
        """
        blocks = []

        # Split content by File: headers
        file_sections = re.split(
            r'(?:^|\n)(?:File|Modify):\s*`?([^\n`]+)`?\s*\n',
            content,
            flags=re.IGNORECASE,
        )

        # file_sections alternates: [preamble, filepath1, body1, filepath2, body2, ...]
        for i in range(1, len(file_sections), 2):
            filepath = file_sections[i].strip()
            body = file_sections[i + 1] if i + 1 < len(file_sections) else ""

            # Find all <<<SEARCH ... === ... >>> blocks in this file's body
            sr_pattern = r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>'
            for match in re.finditer(sr_pattern, body, re.DOTALL):
                search_text = match.group(1)
                replace_text = match.group(2)
                blocks.append({
                    'file': filepath,
                    'search': search_text,
                    'replace': replace_text,
                })

        return blocks
    ```

### Source Context Injection

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 3 — Add `extract_modify_files()` and `build_source_context()` functions**

- Add two new functions after `parse_search_replace_blocks()`:

    ```python
    def extract_modify_files(runbook_content: str) -> List[str]:
        """
        Scan runbook content for [MODIFY] markers and extract file paths.

        Looks for patterns like:
            #### [MODIFY] .agent/src/agent/commands/implement.py

        Returns:
            List of file path strings referenced by [MODIFY] markers.
        """
        pattern = r'\[MODIFY\]\s*`?([^\n`]+)`?'
        matches = re.findall(pattern, runbook_content, re.IGNORECASE)
        # Deduplicate while preserving order
        seen = set()
        result = []
        for path in matches:
            path = path.strip()
            if path not in seen:
                seen.add(path)
                result.append(path)
        return result


    def build_source_context(file_paths: List[str]) -> str:
        """
        Build source context string by reading current file contents.

        Files exceeding SOURCE_CONTEXT_MAX_LOC are truncated to
        first/last SOURCE_CONTEXT_HEAD_TAIL lines with an omission marker.

        Args:
            file_paths: List of repo-relative file paths to read.

        Returns:
            Formatted string containing file contents for prompt injection.
        """
        context_parts = []

        for filepath in file_paths:
            resolved = resolve_path(filepath)
            if not resolved or not resolved.exists():
                logging.warning(
                    "source_context_skip file=%s reason=not_found", filepath
                )
                continue

            try:
                content = resolved.read_text()
            except Exception as e:
                logging.warning(
                    "source_context_skip file=%s reason=%s", filepath, e
                )
                continue

            lines = content.splitlines()
            loc = len(lines)

            if loc > SOURCE_CONTEXT_MAX_LOC:
                head = "\n".join(lines[:SOURCE_CONTEXT_HEAD_TAIL])
                tail = "\n".join(lines[-SOURCE_CONTEXT_HEAD_TAIL:])
                omitted = loc - (2 * SOURCE_CONTEXT_HEAD_TAIL)
                truncated_content = (
                    f"{head}\n"
                    f"... ({omitted} lines omitted) ...\n"
                    f"{tail}"
                )
                context_parts.append(
                    f"### Current content of `{filepath}` "
                    f"({loc} LOC — truncated):\n"
                    f"```\n{truncated_content}\n```\n"
                )
            else:
                context_parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC):\n"
                    f"```\n{content}\n```\n"
                )

        return "\n".join(context_parts)
    ```

### Merge-Aware Apply

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 4 — Add `apply_search_replace_to_file()` function**

- Add a new function before `apply_change_to_file()` (before line 565):

    ```python
    def apply_search_replace_to_file(
        filepath: str,
        blocks: List[Dict[str, str]],
        yes: bool = False,
    ) -> tuple[bool, str]:
        """
        Apply search/replace blocks surgically to an existing file.

        Each block must match exactly. If any block fails to match,
        the entire operation is aborted — no partial apply.

        Args:
            filepath: Repo-relative file path.
            blocks: List of dicts with 'search' and 'replace' keys.
            yes: Skip confirmation prompts.

        Returns:
            Tuple of (success: bool, final_content: str).
            On failure, final_content is the original unchanged content.
        """
        resolved_path = resolve_path(filepath)
        if not resolved_path or not resolved_path.exists():
            console.print(
                f"[bold red]❌ Cannot apply search/replace to "
                f"'{filepath}': file not found.[/bold red]"
            )
            return False, ""

        original_content = resolved_path.read_text()
        working_content = original_content

        # Dry-run: verify all blocks match before applying any
        for i, block in enumerate(blocks):
            if block['search'] not in working_content:
                console.print(
                    f"[bold red]❌ Search block {i+1}/{len(blocks)} "
                    f"not found in {filepath}.[/bold red]"
                )
                console.print(
                    f"[dim]Expected to find:[/dim]\n"
                    f"[red]{block['search'][:200]}...[/red]"
                )
                logging.warning(
                    "search_replace_match_failure file=%s block=%d/%d",
                    filepath, i + 1, len(blocks),
                )
                return False, original_content

            # Warn if search text is ambiguous (appears multiple times)
            match_count = working_content.count(block['search'])
            if match_count > 1:
                console.print(
                    f"[yellow]⚠️  Search block {i+1} matches "
                    f"{match_count} locations in {filepath}. "
                    f"Replacing first occurrence only.[/yellow]"
                )
                logging.warning(
                    "search_replace_ambiguous file=%s block=%d/%d "
                    "match_count=%d",
                    filepath, i + 1, len(blocks), match_count,
                )

            # Apply this block to working content (for subsequent matches)
            working_content = working_content.replace(
                block['search'], block['replace'], 1
            )

        # Show diff preview
        console.print(f"\n[bold cyan]📝 Search/Replace for: {filepath}[/bold cyan]")
        console.print(
            f"[dim]Applying {len(blocks)} search/replace block(s)[/dim]"
        )

        # Show unified diff (uses module-level difflib import)
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            working_content.splitlines(keepends=True),
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
        ))
        if diff_lines:
            diff_text = "".join(diff_lines)
            syntax = Syntax(diff_text, "diff", theme="monokai")
            console.print(syntax)

        # Confirmation
        if not yes:
            response = typer.confirm(
                f"\nApply {len(blocks)} search/replace block(s) to "
                f"{filepath}?",
                default=False,
            )
            if not response:
                console.print("[yellow]⏭️  Skipped[/yellow]")
                return False, original_content

        # Backup and write
        backup_path = backup_file(resolved_path)
        if backup_path:
            console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")

        try:
            resolved_path.write_text(working_content)
            console.print(
                f"[bold green]✅ Applied {len(blocks)} search/replace "
                f"block(s) to {filepath}[/bold green]"
            )

            # Structured logging (NFR)
            logging.info(
                "apply_change apply_mode=search_replace file=%s "
                "blocks=%d lines_changed=%d",
                filepath, len(blocks),
                count_edit_distance(original_content, working_content),
            )

            # Log the change
            log_file = Path(".agent/logs/implement_changes.log")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().isoformat()
            with open(log_file, "a") as f:
                f.write(
                    f"[{timestamp}] SearchReplace: {filepath} "
                    f"({len(blocks)} blocks)\n"
                )

            return True, working_content
        except Exception as e:
            console.print(
                f"[bold red]❌ Failed to write file: {e}[/bold red]"
            )
            return False, original_content
    ```

**Step 5 — Add file size guard to `apply_change_to_file()`**

- Modify `apply_change_to_file()` (lines 565–625) to add the `legacy_apply` parameter and file size guard:

    Replace the function signature and add the size guard check after the path resolution:

    ```python
    def apply_change_to_file(
        filepath: str,
        content: str,
        yes: bool = False,
        legacy_apply: bool = False,
    ) -> bool:
        """
        Apply code changes to a file with smart path resolution.

        For existing files exceeding FILE_SIZE_GUARD_THRESHOLD, rejects
        full-file overwrites unless legacy_apply is True (AC-5).
        """
        resolved_path = resolve_path(filepath)
        if not resolved_path:
            return False

        file_path = resolved_path
        filepath = str(resolved_path)

        # AC-5: File size guard for existing files
        if file_path.exists() and not legacy_apply:
            try:
                existing_lines = len(file_path.read_text().splitlines())
            except Exception:
                existing_lines = 0

            if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
                console.print(
                    f"\n[bold red]❌ Rejected full-file overwrite for "
                    f"{filepath} ({existing_lines} LOC > "
                    f"{FILE_SIZE_GUARD_THRESHOLD} threshold).[/bold red]"
                )
                console.print(
                    "[yellow]The AI must use search/replace format for "
                    "large existing files, or use --legacy-apply to "
                    "bypass.[/yellow]"
                )
                logging.warning(
                    "apply_change apply_mode=rejected file=%s "
                    "file_loc=%d threshold=%d",
                    filepath, existing_lines, FILE_SIZE_GUARD_THRESHOLD,
                )
                return False

        # --- Original logic below (unchanged) ---
    ```

    The rest of the function body (show diff preview, confirmation, backup, write) remains unchanged. Add structured logging after the successful write (before the `return True`):

    ```python
            # Structured logging (NFR — INFRA-096)
            logging.info(
                "apply_change apply_mode=full_file file=%s "
                "lines_changed=%d",
                filepath, len(content.splitlines()),
            )
    ```

### Prompt Updates

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 6 — Update full-context system prompt to use search/replace format**

- In the `implement()` function, replace the output format section of the full-context system prompt (lines 885–895) with:

    ```python
    - **OUTPUT FORMAT for EXISTING files** — emit search/replace blocks:

    File: path/to/existing_file.py
    <<<SEARCH
    exact lines to find in the current file
    ===
    replacement lines
    >>>

    You may emit multiple <<<SEARCH...>>> blocks per file.

    - **OUTPUT FORMAT for NEW files** — emit complete file content:

    File: path/to/new_file.py
    ```python
    # Complete file content here
    ```

  - NEVER emit complete file content for files listed in SOURCE CONTEXT below.
      Use search/replace blocks to make surgical changes.
  - Include all necessary imports in your search/replace blocks.
  - Documentation files (CHANGELOG.md, README.md) should use search/replace if they already exist.
  - Test files should follow the patterns in .agent/tests/.

    ```

**Step 7 — Update chunked system prompt to use search/replace format**

- In the chunked processing path, replace the output format section of `chunk_system_prompt` (lines 966–972) with the same search/replace instructions as Step 6 (adapted for chunk context).

### Source Context Injection into Prompts

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 8 — Inject source context into full-context user prompt**

- Before the `user_prompt` construction (line 897), add source context extraction:

    ```python
            # INFRA-096: Inject source context for files being modified
            modify_files = extract_modify_files(runbook_content_scrubbed)
            source_context = ""
            if modify_files:
                source_context = build_source_context(modify_files)
                source_ctx_chars = len(source_context)
                console.print(
                    f"[dim]📄 Injected source context for "
                    f"{len(modify_files)} file(s) "
                    f"({source_ctx_chars} chars)[/dim]"
                )
                # Token budget warning (NFR)
                total_estimate = (
                    len(system_prompt) + len(runbook_content_scrubbed)
                    + source_ctx_chars + 5000  # overhead estimate
                )
                if total_estimate > 80000:  # ~80% of 100k char window
                    logging.warning(
                        "token_budget_warning total_chars=%d "
                        "threshold=80000",
                        total_estimate,
                    )
                    console.print(
                        f"[yellow]⚠️  Prompt size ({total_estimate} chars) "
                        f"approaching context window limit.[/yellow]"
                    )
    ```

- Then add `source_context` to the `user_prompt` f-string:

    ```python
            user_prompt = f"""RUNBOOK CONTENT:
    {runbook_content_scrubbed}

    SOURCE CONTEXT (Current file contents for files being modified):
    {source_context}

    IMPLEMENTATION GUIDE:
    {guide_content}

    GOVERNANCE RULES:
    {rules_content}

    DETAILED ROLE INSTRUCTIONS:
    {instructions_content}

    ARCHITECTURAL DECISIONS (ADRs):
    {adrs_content}
    """
    ```

**Step 9 — Inject source context into chunked user prompt**

- In the chunked processing path, before the `chunk_user_prompt` construction (line 973), extract modify files from the current chunk:

    ```python
                # INFRA-096: Per-chunk source context
                chunk_modify_files = extract_modify_files(chunk)
                chunk_source_context = ""
                if chunk_modify_files:
                    chunk_source_context = build_source_context(
                        chunk_modify_files
                    )
                    console.print(
                        f"[dim]📄 Source context: "
                        f"{len(chunk_modify_files)} file(s) "
                        f"({len(chunk_source_context)} chars)[/dim]"
                    )
    ```

- Then add `chunk_source_context` to the `chunk_user_prompt`:

    ```python
                chunk_user_prompt = f"""GLOBAL RUNBOOK CONTEXT (Truncated):
    {global_runbook_context[:8000]}

    --------------------------------------------------------------------------------
    CURRENT TASK:
    {chunk}
    --------------------------------------------------------------------------------

    SOURCE CONTEXT (Current file contents):
    {chunk_source_context}

    RULES (Filtered):
    {filtered_rules}

    DETAILED ROLE INSTRUCTIONS:
    {instructions_content}

    ARCHITECTURAL DECISIONS (ADRs):
    {adrs_content}
    """
    ```

### Apply Loop Updates

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 10 — Update chunked apply loop to handle search/replace blocks**

- In the chunked apply loop (lines 1011–1034), after `if apply:`, add search/replace parsing and apply BEFORE the existing `parse_code_blocks` call:

    ```python
                # --- Apply search/replace blocks first (INFRA-096) ---
                sr_blocks = parse_search_replace_blocks(chunk_result)
                if sr_blocks:
                    # Group blocks by file (uses module-level defaultdict import)
                    sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
                    for block in sr_blocks:
                        sr_by_file[block['file']].append(block)

                    console.print(
                        f"[dim]Found {len(sr_blocks)} search/replace "
                        f"block(s) across {len(sr_by_file)} file(s)[/dim]"
                    )

                    for sr_filepath, file_blocks in sr_by_file.items():
                        file_path = Path(sr_filepath)
                        original_content = ""
                        if file_path.exists():
                            try:
                                original_content = file_path.read_text()
                            except Exception:
                                pass

                        success, final_content = apply_search_replace_to_file(
                            sr_filepath, file_blocks, yes,
                        )

                        if success:
                            block_loc = count_edit_distance(
                                original_content, final_content
                            )
                            step_loc += block_loc
                            step_modified_files.append(sr_filepath)

                # --- Then apply full-file code blocks (existing path) ---
    ```

- Ensure the existing `parse_code_blocks` + `apply_change_to_file` loop now passes `legacy_apply`:

    ```python
                code_blocks = parse_code_blocks(chunk_result)
                if code_blocks:
                    # Filter out files already handled by search/replace
                    sr_handled = {b['file'] for b in sr_blocks} if sr_blocks else set()
                    code_blocks = [
                        b for b in code_blocks
                        if b['file'] not in sr_handled
                    ]

                    if code_blocks:
                        console.print(
                            f"[dim]Found {len(code_blocks)} full-file "
                            f"block(s) in this task[/dim]"
                        )
                        for block in code_blocks:
                            file_path = Path(block['file'])
                            original_content = ""
                            if file_path.exists():
                                try:
                                    original_content = file_path.read_text()
                                except Exception:
                                    pass

                            success = apply_change_to_file(
                                block['file'], block['content'], yes,
                                legacy_apply=legacy_apply,
                            )
                            if success:
                                block_loc = count_edit_distance(
                                    original_content, block['content']
                                )
                                step_loc += block_loc
                                step_modified_files.append(block['file'])
    ```

**Step 11 — Update full-context apply loop to handle search/replace blocks**

- In the full-context apply path (lines 1143–1148), replace the simple loop with dual-format handling:

    ```python
        elif apply and not fallback_needed:
            console.print("\n[bold blue]🔧 Applying changes...[/bold blue]")

            # INFRA-096: Handle search/replace blocks first
            sr_blocks = parse_search_replace_blocks(full_content)
            if sr_blocks:
                # Uses module-level defaultdict import
                sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
                for block in sr_blocks:
                    sr_by_file[block['file']].append(block)

                for sr_filepath, file_blocks in sr_by_file.items():
                    apply_search_replace_to_file(
                        sr_filepath, file_blocks, yes,
                    )

            # Then handle full-file code blocks
            sr_handled = {b['file'] for b in sr_blocks} if sr_blocks else set()
            code_blocks = [
                b for b in parse_code_blocks(full_content)
                if b['file'] not in sr_handled
            ]
            for block in code_blocks:
                apply_change_to_file(
                    block['file'], block['content'], yes,
                    legacy_apply=legacy_apply,
                )
    ```

### CLI Flag

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 12 — Add `--legacy-apply` CLI flag to `implement()`**

- Add the `legacy_apply` parameter to the `implement()` function signature (after `skip_security`, around line 726):

    ```python
        legacy_apply: bool = typer.Option(
            False, "--legacy-apply",
            help="Bypass safe-apply protections (full-file overwrite allowed). Audit-logged.",
        ),
    ```

- After the existing skip audit logging (around line 831), add legacy-apply audit logging:

    ```python
        if legacy_apply:
            gates.log_skip_audit("Safe apply bypass", story_id)
            console.print(
                f"⚠️  [AUDIT] Safe-apply protections bypassed at "
                f"{datetime.now().isoformat()}"
            )
    ```

## Verification Plan

### Automated Tests

#### [NEW] .agent/tests/commands/test_implement_safe_apply.py

> **Fixture Note**: All tests MUST mock `subprocess.run` for git operations and `ai_service.complete` for AI responses. Use `tmp_path` for file operations.

**Parser Tests:**

- **Test 1: `parse_search_replace_blocks` — single block** — Input with one `File:` header and one `<<<SEARCH...>>>` block. Assert returns 1 block with correct `file`, `search`, `replace`.

- **Test 2: `parse_search_replace_blocks` — multiple blocks per file** — Input with one `File:` header and two `<<<SEARCH...>>>` blocks. Assert returns 2 blocks, both with same `file`.

- **Test 3: `parse_search_replace_blocks` — multiple files** — Input with two `File:` headers, each with one block. Assert returns 2 blocks with different `file` values.

- **Test 4: `parse_search_replace_blocks` — mixed with code blocks** — Input containing both search/replace blocks and traditional ```` ```python ```` code blocks. Assert only search/replace blocks are returned (code blocks are handled by `parse_code_blocks`).

- **Test 5: `parse_search_replace_blocks` — empty/malformed** — Input with no search/replace blocks. Assert returns empty list. Input with missing `===`. Assert returns empty list.

**Source Context Tests:**

- **Test 6: `extract_modify_files` — standard markers** — Input runbook with `#### [MODIFY] path/to/file.py`. Assert returns `["path/to/file.py"]`.

- **Test 7: `extract_modify_files` — deduplication** — Input with same file referenced twice. Assert returns it once.

- **Test 8: `build_source_context` — small file** — Create a 50-line file in `tmp_path`. Assert output contains full file content with LOC annotation.

- **Test 9: `build_source_context` — large file truncation** — Create a 500-line file in `tmp_path`. Assert output contains first 100 lines, omission marker with `(300 lines omitted)`, and last 100 lines.

- **Test 10: `build_source_context` — missing file** — Pass a non-existent path. Assert returns empty string. Assert `logging.warning` called.

**Apply Tests:**

- **Test 11: `apply_search_replace_to_file` — happy path** — Create a file with known content. Apply one search/replace block. Assert file content updated correctly.

- **Test 12: `apply_search_replace_to_file` — no match (AC-6)** — Create a file. Attempt to apply a search block that doesn't exist. Assert returns `(False, original_content)`. Assert error message printed. Assert file content unchanged.

- **Test 13: `apply_search_replace_to_file` — multiple blocks in order** — Create a file. Apply 3 search/replace blocks. Assert all applied in sequence, final content correct.

- **Test 14: `apply_search_replace_to_file` — second block fails (rollback)** — Create a file. First block matches, second doesn't. Assert returns `(False, original_content)`. Assert file content unchanged (no partial apply).

**Size Guard Tests:**

- **Test 15: `apply_change_to_file` — small file accepted** — Create a 100-line file. Call with full-file content. Assert returns `True`.

- **Test 16: `apply_change_to_file` — large file rejected (AC-5)** — Create a 250-line file. Call with full-file content. Assert returns `False`. Assert rejection message printed.

- **Test 17: `apply_change_to_file` — new file accepted (AC-7)** — Call with filepath that doesn't exist. Assert returns `True`, file created.

- **Test 18: `apply_change_to_file` — legacy bypass (AC-5 + AC-8)** — Create a 250-line file. Call with `legacy_apply=True`. Assert returns `True` (file size guard bypassed). Note: `log_skip_audit` is called in `implement()` not `apply_change_to_file()` — test the flag-level audit in an integration test.

**Edge Case Tests (Panel Recommendation):**

- **Test 19: `apply_search_replace_to_file` — duplicate match (ambiguous)** — Create a file where `block['search']` appears twice. Assert the first occurrence is replaced. Assert ambiguity warning is logged.

- **Test 20: `apply_search_replace_to_file` — empty replacement (deletion)** — Create a file with 10 lines. Apply a search/replace block where `replace` is an empty string. Assert the search text is removed and file is shorter.

- **Test 21: `apply_search_replace_to_file` — overlapping/chained blocks** — Create a file. Block 1 replaces `foo` with `bar`. Block 2's search text contains `bar` (the result of block 1). Assert both blocks applied correctly in sequence.

- [ ] `pytest .agent/tests/commands/test_implement_safe_apply.py`

### Manual Verification

- [ ] Run `agent implement INFRA-096 --apply --yes` on a story modifying a 500+ LOC file and verify:
  - Source context appears in the console output (`📄 Injected source context...`)
  - AI returns search/replace blocks (inspect the AI output log)
  - Search/replace blocks are applied surgically (check `git diff`)
  - Full-file overwrites for large files are rejected with clear error message
- [ ] Run with `--legacy-apply` flag and verify:
  - Full-file overwrite proceeds for large files
  - Audit log entry appears in `agent.log`
- [ ] Run on a story that only creates new files and verify:
  - Full-file content is accepted (no search/replace needed)
  - Existing behavior is preserved
- [ ] Check `agent.log` for structured entries: `apply_mode=search_replace`, `apply_mode=full_file`, `apply_mode=rejected`

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-096 entry under "Added".
- [ ] README.md updated (if applicable) — likely N/A for internal CLI enhancement.
- [ ] CLI help text for `--legacy-apply` flag is accurate.

### Observability

- [ ] Logs are structured and free of PII.
- [ ] Apply decisions logged with `apply_mode`, `file`, `lines_changed`.
- [ ] Token budget warnings logged when prompt exceeds 80% of context window.
- [ ] OpenTelemetry spans added: `implement.apply_change`, `implement.parse_search_replace`, `implement.inject_source_context`.

### Testing

- [ ] Unit tests passed (`test_implement_safe_apply.py`).
- [ ] Existing implement tests still pass (`test_implement.py`, `test_implement_branching.py`, `test_implement_circuit_breaker.py`, `test_implement_pathing.py`, `test_implement_updates_journey.py`).

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
