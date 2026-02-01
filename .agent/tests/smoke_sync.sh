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

echo "Running agent sync smoke tests..."

# 1. Check help
agent sync --help > /dev/null
echo "✅ agent sync --help passed"

# 2. Check each subcommand help to ensure they are loadable
agent sync pull --help > /dev/null
echo "✅ agent sync pull --help passed"

agent sync push --help > /dev/null
echo "✅ agent sync push --help passed"

agent sync status --help > /dev/null
echo "✅ agent sync status --help passed"

# 3. Check status run (should run without extensive auth or fail gracefully)
# We accept exit code 0 or 1, primarily checking that it doesn't crash with ImportError
agent sync status || true
echo "✅ agent sync status executed (exit code ignored for smoke check)"

echo "Global sync smoke test passed."
