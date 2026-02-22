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

import os
from pathlib import Path

def get_commented_header(header_text, ext):
    lines = header_text.strip().split('\n')
    
    # Python, Shell, YAML, Ruby, etc.
    if ext in ['.py', '.sh', '.yaml', '.yml', '.rb']:
        return '\n'.join([f"# {line}" if line else "#" for line in lines]) + '\n\n'
    
    # JavaScript, TypeScript, CSS, Java, Swift, Kotlin, etc.
    elif ext in ['.js', '.jsx', '.ts', '.tsx', '.css', '.java', '.swift', '.kt', '.go', '.c', '.cpp', '.h', '.hpp']:
        out = "/*\n"
        out += '\n'.join([f" * {line}" if line else " *" for line in lines])
        out += "\n */\n\n"
        return out
    
    # HTML, XML
    elif ext in ['.html', '.xml']:
        out = "<!--\n"
        out += '\n'.join([f"  {line}" if line else "" for line in lines])
        out += "\n-->\n\n"
        return out
        
    return ""

def main():
    repo_root = Path(__file__).resolve().parent.parent
    template_path = repo_root / '.agent' / 'templates' / 'license_header.txt'
    
    with open(template_path, 'r') as f:
        header_text = f.read()
        
    # Standard source extensions
    extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.css', '.sh', '.swift', '.kt'}
    
    # Exclude directories
    exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 
                    '.ruff_cache', '.agent/cache', '.gemini', 'tmp'}
                    
    updated_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(repo_root):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not any(root.replace(str(repo_root), '').startswith(f"/{ex}") for ex in exclude_dirs)]
        
        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix
            
            if ext not in extensions:
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    continue
            
            # Check if it already has the license header (or a part of it)
            if "Copyright 2026 Justin Cook" in content or "Licensed under the Apache License" in content:
                skipped_count += 1
                continue
                
            # Prepend header
            commented_header = get_commented_header(header_text, ext)
            if not commented_header:
                continue
                
            # Handle shebangs
            if content.startswith('#!'):
                lines = content.split('\n')
                shebang = lines[0] + '\n'
                rest = '\n'.join(lines[1:])
                new_content = shebang + '\n' + commented_header + rest
            else:
                new_content = commented_header + content
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            updated_count += 1

    print(f"Successfully added license header to {updated_count} files.")
    print(f"Skipped {skipped_count} files (already had header).")

if __name__ == '__main__':
    main()
