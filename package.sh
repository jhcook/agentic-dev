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
DIST_DIR="dist"
ARCHIVE_NAME="agent-release.tar.gz"
SOURCE_DIR=".agent"

# Ensure we are in the root
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: .agent directory not found. Please run this script from the repository root."
    exit 1
fi

# Create dist directory
mkdir -p "$DIST_DIR"

echo "🧹 Cleaning temporary files..."
find "$SOURCE_DIR" -name "__pycache__" -type d -exec rm -rf {} +
find "$SOURCE_DIR" -name "*.pyc" -delete
find "$SOURCE_DIR" -name ".DS_Store" -delete
find "$SOURCE_DIR" -name ".pytest_cache" -type d -exec rm -rf {} +
find "$SOURCE_DIR" -name ".ruff_cache" -type d -exec rm -rf {} +

rm -rf dist/build dist/$ARCHIVE_NAME $SOURCE_DIR/bin/agent

# Stamp Version
echo "🔖 Stamping version..."
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # Ensure src directory exists to avoid errors if it doesn't
    mkdir -p .agent/src
    git describe --tags --always --dirty > .agent/src/VERSION
else
    echo "unknown" > .agent/src/VERSION
fi

echo "📦 Compile the agent binary..."
echo "   Compiling with PyInstaller..."
cd .agent
# Get PyInstaller via uv if available, falling back to uv run
uv pip install pyinstaller
uv run pyinstaller --onefile --name agent \
    --collect-all rich \
    --add-data "$(pwd)/src/VERSION:." \
    src/agent/main.py --distpath ../dist/bin --workpath ../dist/build --specpath ../dist/
cd ..

# list tracked files
git ls-files "$SOURCE_DIR" > "$DIST_DIR/files_to_package.txt"

# Add version file
echo ".agent/src/VERSION" >> "$DIST_DIR/files_to_package.txt"
# Add compiled binary
echo "dist/bin/agent" >> "$DIST_DIR/files_to_package.txt"

echo "📦 Packaging agent..."
# We use -T - to read files from stdin
# Exclude raw python code and build artifacts
grep -v "/tests/" "$DIST_DIR/files_to_package.txt" \
    | grep -v "/test_"          \
    | grep -v "/conftest.py"    \
    | grep -v "\.agent/cache/"   \
    | grep -v "\.agent/adrs/"    \
    | grep -v "\.agent/scripts/" \
    | grep -v "\.agent/backups/" \
    | grep -v "\.agent/logs/"    \
    | grep -v "\.agent/secrets/" \
    | grep -v "\.agent/storage/" \
    | grep -v "\.agent/\.venv/"   \
    | grep -v "\.agent/Makefile" \
    | grep -v "\.agent/src/" \
    | grep -v "pyproject\.toml" \
    | grep -v "uv\.lock" \
    | grep -v "\.agent/bin/agent" \
    | tar -czf "$DIST_DIR/$ARCHIVE_NAME" -T -

echo "✅ Build complete!"
echo "   Archive: $DIST_DIR/$ARCHIVE_NAME"
echo "   Size: $(du -h "$DIST_DIR/$ARCHIVE_NAME" | cut -f1)"

echo ""
echo "To install in another repo:"
echo "   tar -xzf $ARCHIVE_NAME -C /path/to/target/repo"
