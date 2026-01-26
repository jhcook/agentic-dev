# STORY-ID: INFRA-039: Enhance Voice Agent Tool Capabilities

## State

ACCEPTED

## Goal Description

Enhance the Voice Agent's capabilities by providing it with deeper understanding of its tools and the underlying codebase, enabling it to answer technical questions, explain functionality, and assist with operational activities more effectively. This involves improving the agent's system prompt, enhancing existing tools with new features (hot reloading, syntax validation, etc.), refactoring tools for clarity, and adding observability measures.

## Panel Review Findings

- **@Architect**: The scope of this story is quite broad, touching several components. We need to ensure the changes are modular and well-isolated to prevent unintended side effects. The hot reloading feature needs careful design to avoid performance issues and potential security vulnerabilities if improperly implemented.  We also need to think about how the system will scale as more tools are added.  Consider adding some kind of indexing or caching of tool metadata.
- **@Security**: The `create_tool` functionality introduces significant code injection risks. While repository root restrictions mitigate some risks, input validation and sanitization are crucial. The user acceptance of RCE risks should be clearly logged. We also need to consider the principle of least privilege – does the agent *need* to create tools, or can tools be pre-approved?  The silent reading feature shouldn't inadvertently expose sensitive information.
- **@QA**: The testing strategy relies heavily on manual verification. We need to add more automated tests, especially for the `create_tool` functionality (syntax validation, hot reloading). We should also consider property-based testing to ensure the system behaves correctly under a wide range of inputs.  A comprehensive suite of integration tests should be added to guarantee new tools can be created, loaded, and executed.
- **@Docs**: The success of this feature hinges on the quality of the tool docstrings. We need to ensure that developers understand the importance of writing clear and comprehensive documentation.  The API documentation for the enhanced tools must be updated. Also, documentation should be added describing how to create new tools and their expected format and content.
- **@Compliance**: The user acceptance of RCE risks needs to be documented and audited. We need to ensure that the tool creation process complies with any internal security policies. Log any sensitive information access. Consider GDPR and PII implications, especially within logs.
- **@Observability**: The logging of created tool content is important for auditing and debugging, but we need to ensure that sensitive information is not inadvertently logged. The tracing of tool execution and creation will be invaluable for understanding performance and identifying potential issues.  Add appropriate metrics around tool creation and usage.

## Implementation Steps

### `backend/voice/orchestrator.py`

#### MODIFY `backend/voice/orchestrator.py`

- Update the system prompt to explicitly detail tool usage strategies and encourage tool-first problem solving.
- Example:

```python
SYSTEM_PROMPT = """
You are a helpful AI assistant that helps developers.
Your primary goal is to assist the user with their requests by using the available tools.
Always prefer to use tools before answering directly.
When asked to perform a task, start by listing the available tools using the list_capabilities tool to get descriptions of all the tools.
Then, use the tools to gather information, and then synthesize the information into a response.
Be concise and avoid unnecessary fluff.
"""
```

### `backend/voice/tools/create_tool.py`

#### MODIFY `backend/voice/tools/create_tool.py`

- Rename `draft_new_tool` to `create_tool`.
- Allow creating tools anywhere within the repository (source control boundary). Use `os.path.join` and validate the final path is within the allowed base directory.
- Implement syntax validation using `ast.parse` before saving to prevent breaking the registry.
- Example:

```python
import os
import ast

def create_tool(file_path: str, code: str) -> str:
    """Creates a new tool in the specified file path.
    The path must be within the repository.  The code is validated
    before it is saved.  If successful, the tool is hot-reloaded.
    """
    base_dir = "."  # Repository root.  Consider making this configurable.
    abs_path = os.path.abspath(os.path.join(base_dir, file_path))
    if not abs_path.startswith(os.path.abspath(base_dir)):
        return "Error: File path is outside the repository boundary."
    try:
        ast.parse(code) # Validate code
    except SyntaxError as e:
        return f"Error: Invalid Python syntax: {e}"
    try:
        with open(abs_path, "w") as f:
            f.write(code)
        # Implement hot-reloading here
        return f"Tool created successfully at {file_path}.  Attempting to hot-reload." #Hot Reload logic goes here
    except Exception as e:
        return f"Error creating tool: {e}"
```

#### NEW `backend/voice/tools/create_tool.py`

- Implement hot reloading of new tools. This may involve importing the new module and updating the tool registry.

### `backend/voice/tools/read_tool_source.py`

#### NEW `backend/voice/tools/read_tool_source.py`

- Implement tool for reading existing tool code.

```python
def read_tool_source(file_path: str) -> str:
    """Reads the source code of a tool from the specified file path."""
    try:
        with open(file_path, "r") as f:
            source_code = f.read()
        return source_code
    except FileNotFoundError:
        return "Error: File not found."
    except Exception as e:
        return f"Error reading tool source: {e}"

```

- Implement logic to ensure the agent does not read code blocks out loud (UX). (Consider special tags, or stripping comments)

### `backend/voice/tools/get_installed_packages.py`

#### NEW `backend/voice/tools/get_installed_packages.py`

- Implement tool to check available libraries.

```python
import pkg_resources

def get_installed_packages() -> str:
    """Returns a list of installed Python packages."""
    installed_packages = pkg_resources.working_set
    packages_list = sorted(["%s==%s" % (i.key, i.version)
                            for i in installed_packages])
    return "\n".join(packages_list)
```

### `backend/voice/tools/list_capabilities.py`

#### MODIFY `backend/voice/tools/list_capabilities.py`

- Return rich metadata (docstrings) for all tools.

### `backend/voice/tools/project.py`

#### MODIFY `backend/voice/tools/project.py`

- Implement actual filtering for `list_stories` and improve docstrings.

### `backend/voice/tools/architect.py`

#### MODIFY `backend/voice/tools/architect.py`

- Ensure `list_adrs` finds all relevant decision records.

### `backend/voice/tools/security.py`

#### MODIFY `backend/voice/tools/security.py`

- Update scan tool to accept file paths for broader usability.

### `backend/voice/tools/qa.py`

#### MODIFY `backend/voice/tools/qa.py`

- Add robustness checks for test runners.

## Verification Plan

### Automated Tests

- [ ] Unit tests for `create_tool` (syntax validation, file creation).
- [ ] Unit tests for `read_tool_source` (file reading).
- [ ] Unit tests for `get_installed_packages` (package listing).
- [ ] Unit tests for filtering logic in `project.py`.
- [ ] Unit tests for `list_adrs` in `architect.py`.
- [ ] Integration test: Create a new tool, verify it is hot-reloaded, and execute it via the agent.
- [ ] Integration tests using the security scan tool on various file types.

### Manual Verification

- [ ] Create a new tool using the voice interface.
- [ ] Verify the tool is created in the correct directory.
- [ ] Verify the tool can be executed via the voice interface.
- [ ] Use the voice interface to read the source code of a tool.
- [ ] Verify that the agent can "explain" what a tool does by reading its source.
- [ ] Use the agent to list stories and ADRs, verifying correct filtering.
- [ ] Run security scans using the updated tool, passing different file paths.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [ ] README.md updated (if applicable)
- [ ] API Documentation updated (if applicable) (Specifically for new tools and modified tools). Add documentation about the format of tool docstrings to enable effective use by the agent. Document how to create a new tool using the voice interface.

### Observability

- [x] Logs are structured and free of PII
- [ ] Metrics added for new features (Tool creation, tool usage frequency, error rates).
- [ ] Log content of created tools (with appropriate redaction of sensitive information, if any. Flag if sensitive information *would* have been logged)
- [ ] Trace tool execution and creation.

### Testing

- [x] Unit tests passed (`tests/test_create_tool.py`)
- [x] Integration tests passed (`tests/test_integration_tools.py`)
  - Validated full lifecycle: Create -> Read (Silent Tag Check) -> Security Scan -> Hot Reload simulation.
  - Validated Security Scanner catches PII (Email, API Keys).

### Security & Compliance

- [x] RCE Risk Acceptance logging implemented.
- [x] PII Scanning implemented (Regex for Email, IP).
- [x] Strict Silent Reading implemented (Tag wrapping + System Instruction).
- [x] Path Traversal protection verified.
- [x] Static Analysis (AST) implemented for dangerous imports.
