# INFRA-016: visualize-project-artifacts

## State
ACCEPTED

## Goal Description
To create a new command `agent visualize` that generates diagrammatic views of the project's governance artifacts (Plans, Stories, Runbooks) and code structure. This command will produce Mermaid syntax to visualize dependencies, helping developers and stakeholders better understand the project's architecture and task relationships.

## Panel Review Findings
- **@Architect**: The proposal to separate graph-building logic (`agent/core/graph.py`) from presentation/CLI logic (`agent/commands/visualize.py`) is sound and promotes good separation of concerns. The "Experimental" scope for the `architecture` view, which avoids complex AST parsing initially, is a pragmatic approach to delivering value incrementally without over-engineering. The core challenge will be designing a robust file discovery and metadata parsing mechanism that can scale without becoming a performance bottleneck, as specified in the NFR (<5s for 1000 nodes). The data model should be flexible enough to accommodate future node and edge types.

- **@Security**: The explicit requirement for the optional `--serve` flag to bind *only* to `localhost` (`127.0.0.1`) is critical and non-negotiable to prevent accidental exposure on the network. The implementation must ensure that file contents are not parsed or displayed in the graph nodes; only file paths and metadata (e.g., Story titles from frontmatter) are used. The sanitization function is important not just for syntax correctness but also as a defense-in-depth measure against potential injection issues if the output is ever used in less-controlled web contexts.

- **@QA**: The test strategy is a solid foundation. It must be expanded to cover edge cases. Unit tests for the graph builder must include scenarios like an empty repository, artifacts without links (e.g., a Plan with no Stories), and correctly handling malformed frontmatter. Integration tests must use a dedicated, version-controlled set of fixture files to ensure repeatability. We need to verify not just successful output but also that the CLI provides clear error messages and non-zero exit codes for failures, such as when a Story ID for the `flow` subcommand is not found.

- **@Docs**: This is a new user-facing feature and requires clear documentation. The command's `--help` output must be comprehensive for the base command and all subcommands (`graph`, `flow`). A new section should be added to the project `README.md` under a "Tooling" or "Usage" heading that explains the `visualize` command and provides examples. The `CHANGELOG.md` must be updated to reflect this new capability.

- **@Compliance**: The current governance rules are not directly applicable. However, the principle of data minimization is. The tool reads project files, and the implementation must strictly adhere to reading only the necessary metadata (frontmatter) and file paths. It must not read or expose the body content of any file. This ensures that any potentially sensitive information within the artifacts is not inadvertently included in the generated diagrams, maintaining compliance with internal data handling policies.

- **@Observability**: As a short-lived CLI process, traditional observability is limited. However, we should implement two key features. First, add a `--verbose` flag that enables structured logging to stderr, detailing which files are being scanned and processed; this is invaluable for debugging. Second, the command should report on its performance upon completion (e.g., "Generated graph with 15 nodes and 14 edges in 120ms"), providing immediate feedback and a way to track the performance NFR over time.

## Implementation Steps
### [NEW] `agent/core/graph.py`
- Create a new file for graph construction logic.
- Define a `ProjectGraph` class.
- Implement a method `build_from_repo(root_path)`:
    - Use `glob` or `os.walk` to find all `PLAN-*.md`, `STORY-*.md`, and `RUNBOOK-*.md` files.
    - For each file, parse its YAML frontmatter to extract metadata (e.g., `id`, `title`, `parent_plan`, `story_id`).
    - Add nodes to the graph for each artifact. A node should contain `id`, `type`, `title`, and `path`.
    - Create edges based on the relationships defined in the frontmatter (e.g., a Story's `parent_plan` links it to a Plan).
    - For runbooks, parse the `Implementation Steps` to find file paths mentioned (e.g., `[MODIFY | NEW | DELETE] [file path]`). Add these files as `code` nodes and link them to the runbook.
    - The class should return a simple data structure of nodes and edges, e.g., `{'nodes': [...], 'edges': [...]}`.

### [NEW] `agent/utils/text.py`
- Create a new file for text utility functions if it doesn't exist.
- **NEW** `sanitize_mermaid_label(text: str) -> str`:
    - This function will prepare a string for safe use as a Mermaid node label.
    - It should replace characters like double quotes (`"`) with their HTML entity (`#quot;`), and escape characters that have special meaning in Mermaid's label syntax.
    ```python
    def sanitize_mermaid_label(text: str) -> str:
        # Mermaid labels are strings enclosed in quotes.
        # We need to escape the quote character itself.
        # Example: "STORY-001: Implement the "Visualize" command"
        # Becomes: "STORY-001: Implement the #quot;Visualize#quot; command"
        text = text.replace('"', '#quot;')
        # Escape other potential problematic characters if needed
        # text = text.replace('(', '\\(').replace(')', '\\)')
        return text
    ```

### [NEW] `agent/commands/visualize.py`
- Create a new file for the CLI command.
- Use the `click` library to define the command structure.
- **Main Command Group**: `@click.group()` for `agent visualize`.
- **`graph` Subcommand**:
    - `@visualize.command()` for `graph`.
    - It should call `ProjectGraph.build_from_repo()`.
    - It will then iterate over the returned nodes and edges to generate Mermaid syntax string.
    - Node format: `ID["Label"]`
    - Hyperlink format: Wrap the node definition in `click ID "URL"`
    ```python
    # Example Mermaid Generation
    output = ["graph TD"]
    repo_url = "https://github.com/your/repo/blob/main/" # Get this dynamically
    for node in graph['nodes']:
        label = f'{node["id"]}: {sanitize_mermaid_label(node["title"])}'
        output.append(f'    {node["id"]}["{label}"]')
        output.append(f'    click {node["id"]} "{repo_url}{node["path"]}" "View File"')

    for edge in graph['edges']:
        output.append(f'    {edge["source"]} --> {edge["target"]}')

    print('\n'.join(output))
    ```
- **`flow` Subcommand**:
    - `@visualize.command()` for `flow`.
    - Takes a `story_id` argument.
    - Builds the full graph, then filters it to show only the target story, its parent plan, its child runbook, and any code files linked to that runbook.
    - Print the resulting Mermaid subgraph to stdout. If the story is not found, print an error to `stderr` and exit with code 1.
- **`--serve` Option**:
    - Add a `--serve` option to the `graph` subcommand.
    - If present, generate the full Mermaid graph and embed it in a simple HTML template.
    - Use Python's built-in `http.server` and `webbrowser` modules.
    - **CRITICAL**: The server must bind to `127.0.0.1` explicitly.
    ```python
    # In the graph command logic
    if serve:
        # ... generate mermaid_content ...
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Project Visualization</title></head>
        <body>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>mermaid.initialize({{startOnLoad:true}});</script>
            <div class="mermaid">{mermaid_content}</div>
        </body>
        </html>
        """
        # ... start http.server on 127.0.0.1, serve the content, open browser ...
    ```

## Verification Plan
### Automated Tests
- [ ] **Unit Test (`test_graph.py`):**
    - [ ] Test `ProjectGraph.build_from_repo` using a fixture directory containing dummy `PLAN`, `STORY`, and `RUNBOOK` files.
    - [ ] Verify correct node and edge creation for a standard Plan -> Story -> Runbook -> File chain.
    - [ ] Test with an orphaned story (no parent plan) to ensure it's still added as a node.
    - [ ] Test with a runbook that modifies multiple files, ensuring all edges are created.
    - [ ] Test with an empty directory; the graph should be empty.
- [ ] **Unit Test (`test_text_utils.py`):**
    - [ ] Test `sanitize_mermaid_label` with a simple string.
    - [ ] Test `sanitize_mermaid_label` with a string containing double quotes.
    - [ ] Test `sanitize_mermaid_label` with a string containing other special characters like parentheses and brackets.
- [ ] **Integration Test (`test_cli_visualize.py`):**
    - [ ] Test `agent visualize --help` and verify the output contains `graph` and `flow`.
    - [ ] Run `agent visualize graph` against the fixture directory and assert that stdout contains expected Mermaid syntax (e.g., `graph TD`, `STORY-001 --> RUNBOOK-001`).
    - [ ] Run `agent visualize flow STORY-001` and verify the output is a valid, smaller Mermaid graph.
    - [ ] Run `agent visualize flow NONEXISTENT-STORY` and assert the command exits with a non-zero status code and prints an error message to stderr.

### Manual Verification
- [ ] Pull the branch and install the agent with the new command.
- [ ] Run `agent visualize graph` on the actual project repository.
- [ ] Copy the stdout and paste it into a new GitHub issue/comment or a VS Code Markdown preview to confirm the diagram renders correctly.
- [ ] Verify that clicking on a node in the rendered diagram navigates to the correct file on GitHub.
- [ ] Run `agent visualize flow <an-existing-story-id>`. Paste the output and verify the subgraph is correct and renders properly.
- [ ] Run `agent visualize graph --serve`.
    - [ ] Verify a browser tab opens to a `localhost` or `127.0.0.1` address.
    - [ ] Verify the diagram renders correctly in the browser.
    - [ ] Use a tool like `netstat` or `lsof` to confirm the Python process is listening on `127.0.0.1` and NOT `0.0.0.0`.

## Definition of Done
### Documentation
- [ ] `CHANGELOG.md` updated with an entry for the new `agent visualize` feature.
- [ ] `README.md` updated with a new section explaining how to use `agent visualize` with examples.
- [ ] API Documentation updated (if applicable) - N/A for this CLI tool.

### Observability
- [ ] Logs are structured and free of PII: A `--verbose` flag is implemented to output debug-level information about file scanning to `stderr`.
- [ ] Metrics added for new features: The command prints a summary to `stderr` upon completion (e.g., "Generated graph with X nodes, Y edges in Z ms").

### Testing
- [ ] Unit tests passed for `graph.py` and `text.py`.
- [ ] Integration tests passed for the `visualize` CLI command, including success and failure cases.