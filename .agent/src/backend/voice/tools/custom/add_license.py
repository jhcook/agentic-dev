# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from langchain_core.tools import tool
import os
import logging

logger = logging.getLogger(__name__)

# Apache 2.0 Template
LICENSE_BODY = """Copyright {year} {owner}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

def format_header(content, comment_style="#"):
    """Formats the license body into the desired comment style."""
    lines = content.strip().split("\n")
    if comment_style == "#":
        return "\n".join([f"# {line}".rstrip() for line in lines]) + "\n\n"
    elif comment_style == "//":
        return "\n".join([f"// {line}".rstrip() for line in lines]) + "\n\n"
    elif comment_style == "/*":
        return "/*\n" + "\n".join([f" * {line}".rstrip() for line in lines]) + "\n */\n\n"
    return content

def get_comment_style(ext):
    """Maps file extension to comment style."""
    style_map = {
        ".py": "#",
        ".sh": "#",
        ".yaml": "#",
        ".yml": "#",
        ".txt": "#",
        ".env": "#",
        ".ts": "//",
        ".tsx": "//",
        ".js": "//",
        ".jsx": "//",
        ".cpp": "//",
        ".h": "//",
        ".css": "/*",
        ".scss": "/*",
        ".less": "/*",
    }
    return style_map.get(ext, "#")

@tool
def add_license(file_path: str) -> str:
    """
    Adds the Apache 2.0 license header to a file if it doesn't already have one.
    Supports Python (#), TypeScript (//), and CSS (/* */) styles.
    
    Args:
        file_path: Absolute path to the file.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"

    # Security Check: Ensure file is within strictly allowed paths (repo root)
    try:
        repo_root = os.getcwd() # Assumes agent runs from root
        abs_path = os.path.abspath(file_path)
        if os.path.commonpath([repo_root, abs_path]) != repo_root:
            return f"Security Error: Access denied. File must be within {repo_root}"
    except Exception as e:
        return f"Security Error: Path validation failed: {e}"
    
    ext = os.path.splitext(file_path)[1].lower()
    comment_style = get_comment_style(ext)
    
    # We use hardcoded values as requested for this project
    header_content = format_header(LICENSE_BODY.format(year="2026", owner="Justin Cook"), comment_style)
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        content = "".join(lines)
        if "Licensed under the Apache License, Version 2.0" in content:
            return f"Success: File already has a license header."
        
        # Check for shebang (common in .py, .sh, .js, .ts scripts)
        header_index = 0
        if lines and lines[0].startswith("#!"):
            header_index = 1
            # Check for second line if it's an encoding comment
            if len(lines) > 1 and ("coding=" in lines[1] or "coding:" in lines[1]):
                header_index = 2
        
        new_lines = lines[:header_index] + [header_content] + lines[header_index:]
        
        with open(file_path, 'w') as f:
            f.writelines(new_lines)
            
        logger.info(f"Added license header to {file_path}")
        return f"Success: License header ({comment_style} style) added to {file_path}"
    except Exception as e:
        logger.error(f"Failed to add license to {file_path}: {e}")
        return f"Error: {e}"
