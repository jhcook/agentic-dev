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
import glob
import subprocess
from agent.core.config import config
from agent.core.utils import find_best_matching_story

@tool
def list_stories(status: str = "OPEN") -> str:
    """
    List user stories filtered by status.
    Args:
        status: Filter (e.g. 'OPEN', 'COMPLETED', 'ALL')
    """
    stories_dir = config.repo_root / ".agent/cache/stories"
    pattern = f"{stories_dir}/**/*.md"
    matches = []
    
    for fpath in glob.glob(pattern, recursive=True):
        try:
             filename = os.path.basename(fpath)
             if status == "ALL":
                 matches.append(filename)
                 continue
                 
             # Check content for status
             with open(fpath, 'r') as f:
                 content = f.read()
                 # Simple check for "Status: <status>" or "State: <status>"
                 # Case insensitive check
                 if f"State: {status}" in content or f"Status: {status}" in content or \
                    f"State:\n{status}" in content or f"Status:\n{status}" in content:
                     matches.append(filename)
        except:
            continue
            
    if not matches:
        return f"No stories found with status '{status}'."
    return "\n".join(matches[:20]) # Limit to 20

@tool
def get_project_info() -> str:
    """
    Get high-level project information (name, version, key deps).
    """
    info = []
    if os.path.exists("pyproject.toml"):
        info.append("Found pyproject.toml (Python Project)")
    if os.path.exists("package.json"):
         info.append("Found package.json (Node Project)")
    if os.path.exists(".agent/etc/agents.yaml"):
         info.append("Governance: Active")
         
    return "\n".join(info)

@tool
def list_runbooks() -> str:
    """List all implementation runbooks."""
    files = glob.glob(str(config.repo_root / ".agent/cache/runbooks/**/*.md"), recursive=True)
    return "\n".join([os.path.basename(f) for f in files])

@tool
def match_current_changes_to_story() -> str:
    """
    Analyze currently staged git changes and identify the most relevant User Story.
    """
    try:
        staged = subprocess.check_output(["git", "diff", "--name-only", "--cached"]).decode().strip()
        if not staged:
            return "No staged changes found. Please stage changes using git add first."
            
        staged_files = staged.replace("\n", " ")
        story_id = find_best_matching_story(staged_files)
        
        if story_id:
            return f"Based on the staged changes ({staged_files}), the matching story is: {story_id}"
        else:
            return "Could not match the staged changes to any existing story."
            
    except Exception as e:
        return f"Error matching story: {e}"

from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def _is_safe_path(path: str) -> bool:
    """
    Ensure path is within the project root.
    """
    try:
        # Resolve absolute paths
        abs_path = os.path.abspath(path)
        root_path = str(config.repo_root)
        
        # Use commonpath to check containment
        return os.path.commonpath([root_path, abs_path]) == root_path
    except Exception:
        return False

@tool
def read_file(path: str) -> str:
    """
    Read the content of any file in the repository.
    Args:
        path: Path to the file relative to the project root.
    """
    with tracer.start_as_current_span("tool.read_file") as span:
        span.set_attribute("file.path", path)
        try:
            if not _is_safe_path(path):
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                span.record_exception(Exception("Path traversal attempt"))
                return "Error: Access denied. Path must be within the project root."
                
            if not os.path.exists(path):
                return f"Error: File '{path}' not found."
                
            if os.path.isdir(path):
                return f"Error: '{path}' is a directory. Use list tools instead."
                
            with open(path, 'r') as f:
                content = f.read()
                
            span.set_attribute("file.size", len(content))
            
            if len(content) > 5000:
                return content[:5000] + "\n... (truncated)"
            return content
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"Error reading file: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """
    Write or overwrite a file in the repository.
    Args:
        path: Path to the file relative to the project root.
        content: The text content to write.
    """
    with tracer.start_as_current_span("tool.write_file") as span:
        span.set_attribute("file.path", path)
        span.set_attribute("file.size", len(content))
        try:
            if not _is_safe_path(path):
                return "Error: Access denied. Path must be within the project root."
            
            # Prevent overwriting critical system files
            forbidden = [".agent/etc/secrets.yaml", ".env", ".git/"]
            if any(f in path for f in forbidden):
                 return "Error: Writing to this sensitive file is restricted."
                 
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
                
            return f"Successfully wrote to {path}"
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"Error writing file: {e}"

@tool
def apply_license_headers(path: str = ".") -> str:
    """
    Recursively apply Apache 2.0 license headers to all .py, .ts, and .tsx files
    in the specified path (defaults to project root).
    Skips files that already have the header.
    """
    HEADER_PY = '''# Copyright 2026 Justin Cook
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
'''

    HEADER_JS = '''/*
 * Copyright 2026 Justin Cook
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
'''

    try:
        updated_count = 0
        skipped_count = 0
        
        # Normalize path
        start_dir = os.path.abspath(path)
        
        for root, dirs, files in os.walk(start_dir):
            if ".venv" in root or "node_modules" in root or ".git" in root or "__pycache__" in root:
                continue
                
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext not in ['.py', '.ts', '.tsx']:
                    continue
                    
                full_path = os.path.join(root, file)
                
                # Determine header type
                if ext == '.py':
                    header = HEADER_PY
                    marker = "Licensed under the Apache License"
                else:
                    header = HEADER_JS
                    marker = "Licensed under the Apache License"
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    if marker in content:
                        skipped_count += 1
                        continue
                        
                    # Prepend
                    new_content = header + "\n" + content
                    
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    updated_count += 1
                except Exception as e:
                    print(f"Failed to process {full_path}: {e}")
                    
        return f"License Application Complete:\n- Updated: {updated_count} files\n- Skipped: {skipped_count} files (already licensed)"
        
    except Exception as e:
        return f"Error applying licenses: {e}"
