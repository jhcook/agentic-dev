# Codebase Navigation and Git Tools

This document provides a reference for the search and version control tools available to the agent. These tools are designed to provide semantic awareness of Python structures and structured data for repository management.

## Search Tools

**find_symbol**

Locates function or class definitions by name using Abstract Syntax Tree (AST) parsing.

**Capabilities**:
- Distinguishes between function definitions (`def`), async function definitions (`async def`), and class definitions (`class`).
- Provides exact line numbers for the start of the definition.
- Filters out plain-text matches in comments or strings, ensuring the result is a functional code element.

**Mechanism**:
1. **Candidate Discovery**: Uses Ripgrep (`rg`) to perform a high-speed text scan of all `.py` files for the pattern `\b(class|def)\s+<name>\b`.
2. **AST Validation**: Parses the Abstract Syntax Tree of candidate files only (lazy loading) to verify the node type and name.

**Language Support**:
- **Primary**: Python (.py)
- **Limitations**: Non-Python files are ignored by the AST parser. If a symbol is requested for a file type other than Python, the tool returns a message indicating that the file type is unsupported.

**Supported Python Versions**:
- Compatible with the host environment syntax (Python 3.8+).

**find_references**

Finds all references to a symbol name across the entire codebase using word-boundary ripgrep search.

**Format**:
`path/to/file.py:line_number:code_snippet`

---

## Git Tools

These tools provide wrappers around standard git operations, returning structured JSON for precise parsing.

**blame**

Provides line-by-line authorship information for a file.

**Output Format**:
Returns a JSON-encoded list of objects:

```json
[
  {
    "commit": "e123456",
    "line": 1,
    "content": "# License Header"
  }
]
