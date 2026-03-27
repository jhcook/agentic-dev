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

# Rollback Script for INFRA-167
# Objective: Revert Agent CLI to the stable v1.x.x release.

echo "[ROLLBACK] Initiating reversion of Agent CLI to v1.x.x..."

# 1. Detect Package Manager and Reinstall Legacy Version
# This manages the lifecycle of the code regardless of language-specific assumptions,
# targeting the known distribution methods for the CLI binary.

if command -v pip &> /dev/null && [ -f "pyproject.toml" ]; then
    echo "[ROLLBACK] Reinstalling v1 legacy series via pip..."
    # Reinstalling the last stable v1 release
    pip install "agent-cli<2.0.0" --force-reinstall
elif command -v npm &> /dev/null && [ -f "package.json" ]; then
    echo "[ROLLBACK] Reinstalling v1 legacy series via npm..."
    npm install agent-cli@1 --save-exact
else
    echo "[ROLLBACK] ERROR: No supported package manager detected for automated rollback."
    echo "[ROLLBACK] Please manually revert to the v1.x.x binary release."
    exit 1
fi

# 2. Cleanup session cache
if [ -d ".agent/cache/session" ]; then
    echo "[ROLLBACK] Clearing session cache to prevent schema mismatch..."
    rm -rf .agent/cache/session/*
fi

# 3. Verify Version State
CURRENT_VER=$(agent --version 2>/dev/null || echo "0.0.0")
echo "[ROLLBACK] Post-rollback version detected: $CURRENT_VER"

if [[ $CURRENT_VER == 1.* ]]; then
    echo "[ROLLBACK] SUCCESS: Reverted to v1 stable binary."
else
    echo "[ROLLBACK] FAILURE: Rollback verification failed. Current version is still $CURRENT_VER."
    exit 1
fi
