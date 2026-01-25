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

@tool
def list_docs() -> str:
    """
    List all general documentation files.
    Returns a list of filenames from .agent/docs.
    """
    docs_dir = ".agent/docs"
    files = glob.glob(f"{docs_dir}/*.md*")
    
    if not files:
        return "No documentation found in .agent/docs."
    
    return "\n".join([os.path.basename(f) for f in files])

@tool
def read_doc(filename: str) -> str:
    """
    Read the content of a specific documentation file.
    Args:
        filename: The basename of the file (e.g., 'getting_started.md')
    """
    target = os.path.join(".agent/docs", filename)
    if not os.path.exists(target):
         # Try finding it in recursive search
         matches = glob.glob(f".agent/docs/**/{filename}", recursive=True)
         if matches:
             target = matches[0]
         else:
             return f"File {filename} not found."
             
    try:
        with open(target, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def search_docs(query: str) -> str:
    """
    Search for a specific term within all documentation files.
    """
    results = []
    files = glob.glob(".agent/docs/**/*.md*", recursive=True)
    for file in files:
        try:
            with open(file, 'r') as f:
                content = f.read()
                if query.lower() in content.lower():
                    results.append(os.path.basename(file))
        except:
            continue
            
    if not results:
        return f"No documentation found containing '{query}'."
    return f"Found '{query}' in: {', '.join(results)}"
