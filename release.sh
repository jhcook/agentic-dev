#!/bin/bash
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

set -e

# Configuration
TARGET_DIR="${1:?Usage: ./release.sh <target_dir>}"
WORKFLOW_FILE="$TARGET_DIR/.github/workflows/global-governance-preflight.yml"

# Ensure we are in the root
if [ ! -f "package.sh" ]; then
    echo "❌ Error: package.sh not found. Please run this script from the repository root."
    exit 1
fi

echo "📦 Packaging Agent..."
./package.sh

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "❌ Error: Target directory $TARGET_DIR not found."
    exit 1
fi

# Deploy
echo "🚀 Deploying to $TARGET_DIR..."

# Ensure target .agent exists
if [ ! -d "$TARGET_DIR/.agent" ]; then
    echo "   Creating $TARGET_DIR/.agent..."
    mkdir -p "$TARGET_DIR/.agent"
fi

# Extract to temp dir
echo "   Extracting payload to temporary directory..."
TEMP_DIR=$(mktemp -d)
tar -xzf dist/agent-release.tar.gz -C "$TEMP_DIR"

# Sync to target
echo "   Syncing to $TARGET_DIR..."
# We use rsync to update files, honoring .gitignore
# -a: archive mode
# -v: verbose
# --filter=':- .gitignore': Use .gitignore rules from target if present
# We also want to ensure we don't delete files in target unless we want to match exact state?
# The user requirement was "overwrite everything in the paths they copy to" but "honor .gitignore".
# rsync will overwrite existing files with same name.
# It will NOT delete extra files in target unless --delete is used (we won't use it for safety).
if [ -f "$TARGET_DIR/.gitignore" ]; then
    rsync -av --filter=':- .gitignore' "$TEMP_DIR/" "$TARGET_DIR/"
else
    # If no .gitignore in target, just sync
    rsync -av "$TEMP_DIR/" "$TARGET_DIR/"
fi

# Cleanup
rm -rf "$TEMP_DIR"

# Create skeleton cache directories (since they were excluded from package)
echo "   Creating skeleton cache directories..."
CONFIGURED_SCOPES="{plans,stories,runbooks}/{INFRA,WEB,MOBILE,BACKEND}"
# We use eval to expand the braces since variables in quotes don't expand braces in bash by default?
# Actually simple explicit expansion is safer or enable brace expansion.
# Let's just run mkdir -p with the brace expansion directly.
mkdir -p "$TARGET_DIR/.agent/cache/"{plans,stories,runbooks,journeys}/{INFRA,WEB,MOBILE,BACKEND}
mkdir -p "$TARGET_DIR/.agent/adrs"

echo "✅ Agent files deployed."

# Update Workflow
echo "🔧 Updating GitHub Workflow in $TARGET_DIR..."
if [ -f "$WORKFLOW_FILE" ]; then
    # We use python for robust text replacement instead of complex sed
    python3 -c "
import sys
from pathlib import Path

p = Path('$WORKFLOW_FILE')
try:
    content = p.read_text()
    
    # Define replacements
    # We want to replace the long pip install list with the simpler local install
    # Current (as seen in file):
    # pip install typer rich pydantic google-genai PyYAML tiktoken openai ruff supabase prometheus_client pytest
    
    old_cmd_snippets = [
        'pip install typer rich pydantic google-genai PyYAML tiktoken openai ruff supabase prometheus_client pytest',
        'pip install typer rich pydantic' # partial match fallback if user changed it slightly?
    ]
    
    new_cmd = 'pip install .agent/[ai]'
    
    updated = False
    
    # 1. Try exact match
    if 'pip install .agent' in content:
        print('ℹ️  Workflow already seems to be updated.')
        sys.exit(0)
        
    for snip in old_cmd_snippets:
        if snip in content:
            # We need to be careful. The snippet might be just part of a line.
            # Let's try to replace the whole line if possible, or just the command.
            # But the file might have 'run: |' then the command on next line.
            pass

    # Let's try a regex for the specific block to be safe
    import re
    
    # Regex to find the pip install line under 'Install Python dependencies'
    # strict match for the specific line we saw
    target_line = 'pip install typer rich pydantic google-genai PyYAML tiktoken openai ruff supabase prometheus_client pytest'
    
    if target_line in content:
        new_content = content.replace(target_line, new_cmd)
        p.write_text(new_content)
        print('✅ Updated pip install command (Exact Match).')
        updated = True
    else:
        print('⚠️  Could not find exact pip install string to replace.')
        print('   Expected: ' + target_line)
        sys.exit(1)

except Exception as e:
    print(f'❌ Error processing workflow file: {e}')
    sys.exit(1)
"
else
    echo "❌ Workflow file not found at $WORKFLOW_FILE"
fi

echo "✨ Release Process Complete!"
