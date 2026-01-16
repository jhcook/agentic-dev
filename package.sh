#!/bin/bash
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


# Stamp Version
echo "🔖 Stamping version..."
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # Ensure src directory exists to avoid errors if it doesn't
    mkdir -p .agent/src
    git describe --tags --always --dirty > .agent/src/VERSION
else
    echo "unknown" > .agent/src/VERSION
fi

echo "📦 Packaging agent..."
# Exclude user-specific data directories but keep the tool structure
tar --exclude="$SOURCE_DIR/logs/*" \
    --exclude="$SOURCE_DIR/adrs/*" \
    --exclude="$SOURCE_DIR/cache/*" \
    --exclude="$SOURCE_DIR/secrets/*" \
    --exclude="$SOURCE_DIR/tests" \
    --exclude="$SOURCE_DIR/.venv" \
    -czf "$DIST_DIR/$ARCHIVE_NAME" \
    "$SOURCE_DIR"

echo "✅ Build complete!"
echo "   Archive: $DIST_DIR/$ARCHIVE_NAME"
echo "   Size: $(du -h "$DIST_DIR/$ARCHIVE_NAME" | cut -f1)"

echo ""
echo "To install in another repo:"
echo "   tar -xzf $ARCHIVE_NAME -C /path/to/target/repo"
