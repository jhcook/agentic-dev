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
TARGET_DIR="$1"
if [ -z "$TARGET_DIR" ]; then
    echo "Usage: ./release.sh <target_dir> [license_file] [--source]"
    exit 1
fi

LICENSE_FILE=""
PACKAGE_ARGS=""
INCLUDE_SOURCE=false

shift
while [ "$#" -gt 0 ]; do
    case "$1" in
        --source)
            INCLUDE_SOURCE=true
            PACKAGE_ARGS="--source"
            ;;
        *)
            LICENSE_FILE="$1"
            ;;
    esac
    shift
done

WORKFLOW_FILE="$TARGET_DIR/.github/workflows/global-governance-preflight.yml"

# Ensure we are in the root
if [ ! -f "package.sh" ]; then
    echo "❌ Error: package.sh not found. Please run this script from the repository root."
    exit 1
fi

if [ -n "$LICENSE_FILE" ] && [ ! -f "$LICENSE_FILE" ]; then
    echo "❌ Error: License file $LICENSE_FILE not found."
    exit 1
fi

echo "📦 Packaging Agent..."
./package.sh $PACKAGE_ARGS

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

# Move the binary from its bundled location (dist/bin) to the target location (.agent/bin) inside the temp dir
if [ -f "$TEMP_DIR/dist/bin/agent" ]; then
    mkdir -p "$TEMP_DIR/.agent/bin"
    mv "$TEMP_DIR/dist/bin/agent" "$TEMP_DIR/.agent/bin/agent"
    rm -rf "$TEMP_DIR/dist"
fi

# Sync to target
echo "   Syncing to $TARGET_DIR..."
# We use rsync to deploy the agent code while preserving project-specific data.
# --delete is ONLY used for code directories (src/, templates/, etc., workflows/, docs/, tests/)
# where we want an exact mirror. Project data (cache/, adrs/, secrets/, logs/) is never deleted.
#
# Strategy:
#   1. Mirror code directories with --delete (renamed/deleted files get cleaned up)
#   2. Sync everything else without --delete (additive only, preserves local data)

# Check if target has a .gitignore to honor
HAS_GITIGNORE=false
if [ -f "$TARGET_DIR/.gitignore" ]; then
    HAS_GITIGNORE=true
fi

# Directories that should be exact mirrors of the release (code, not data)
CODE_DIRS="src templates etc workflows docs tests"

for dir in $CODE_DIRS; do
    if [ -d "$TEMP_DIR/.agent/$dir" ]; then
        mkdir -p "$TARGET_DIR/.agent/$dir"
        if [ "$HAS_GITIGNORE" = true ]; then
            rsync -av --delete --filter=':- .gitignore' "$TEMP_DIR/.agent/$dir/" "$TARGET_DIR/.agent/$dir/"
        else
            rsync -av --delete "$TEMP_DIR/.agent/$dir/" "$TARGET_DIR/.agent/$dir/"
        fi
    fi
done

# Sync remaining .agent files (bin, top-level configs) without --delete
# Exclude the code dirs we already handled
EXCLUDE_ARGS=""
for dir in $CODE_DIRS; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$dir/"
done
if [ "$HAS_GITIGNORE" = true ]; then
    rsync -av --filter=':- .gitignore' $EXCLUDE_ARGS "$TEMP_DIR/.agent/" "$TARGET_DIR/.agent/"
else
    rsync -av $EXCLUDE_ARGS "$TEMP_DIR/.agent/" "$TARGET_DIR/.agent/"
fi

# Sync any top-level files from the package (e.g., docs/) without --delete
rsync -av --ignore-existing --exclude '.agent/' "$TEMP_DIR/" "$TARGET_DIR/"

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

if [ -n "$LICENSE_FILE" ]; then
    echo "📄 Copying custom license file..."
    cp "$LICENSE_FILE" "$TARGET_DIR/.agent/templates/license_header.txt"
fi

echo "✅ Agent files deployed."

# Update Workflow
if [ "$INCLUDE_SOURCE" = false ]; then
    echo "🔧 Updating GitHub Workflow in $TARGET_DIR for binary usage..."
    if [ -f "$WORKFLOW_FILE" ]; then
    # We use python for robust text replacement instead of complex sed
    python3 -c "
import sys
import re
from pathlib import Path

p = Path('$WORKFLOW_FILE')
try:
    content = p.read_text()
    
    # 1. Replace the pip install step with chmod
    old_cmd_snippets = [
        'pip install typer rich pydantic google-genai PyYAML tiktoken openai ruff supabase prometheus_client pytest',
        'pip install .agent/[ai]',
        'pip install .agent/'
    ]
    
    new_cmd = 'chmod +x .agent/bin/agent'
    
    updated_deps = False
    for snip in old_cmd_snippets:
        if snip in content:
            content = content.replace(snip, new_cmd)
            print('✅ Updated pip install command to chmod +x.')
            updated_deps = True
            break
            
    if not updated_deps and new_cmd in content:
        print('ℹ️  Workflow pip install command already updated.')
    elif not updated_deps:
        print('⚠️  Could not find pip install string to replace.')

    # 2. Replace the python execution step with binary execution
    old_exec = 'python .agent/src/agent/main.py'
    new_exec = './.agent/bin/agent'
    
    if old_exec in content:
        content = content.replace(old_exec, new_exec)
        print('✅ Updated agent execution command to use binary.')
    elif new_exec in content:
        print('ℹ️  Workflow execution command already updated.')
    else:
        print('⚠️  Could not find agent execution string to replace.')

    p.write_text(content)

except Exception as e:
    print(f'❌ Error processing workflow file: {e}')
    sys.exit(1)
"
    else
        echo "⚠️ Workflow file not found at $WORKFLOW_FILE"
    fi
else
    echo "ℹ️  Source mode enabled; skipping GitHub Workflow binary conversion."
fi

echo "✨ Release Process Complete!"
