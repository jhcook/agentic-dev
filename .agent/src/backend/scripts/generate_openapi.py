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

"""Generate OpenAPI JSON and YAML specs from the backend FastAPI app."""

import json
import sys
from pathlib import Path

import yaml

# Resolve repo root robustly from this script's location:
# .agent/src/backend/scripts/generate_openapi.py -> repo root
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]  # scripts -> backend -> src -> .agent -> repo root

# Verify we found the right root by checking for the .agent marker directory
if not (_REPO_ROOT / ".agent").is_dir():
    raise RuntimeError(
        f"Could not locate repo root (expected .agent/ at {_REPO_ROOT}). "
        "Run this script from within the repository."
    )

# Add src to path to import backend
sys.path.insert(0, str(_REPO_ROOT / ".agent" / "src"))

# Add Premium Addon to path (for OpenAPI generation)
_PREMIUM_PYTHON = _REPO_ROOT / "agentic-executive" / "python"
if _PREMIUM_PYTHON.is_dir():
    sys.path.insert(0, str(_PREMIUM_PYTHON))

from unittest.mock import MagicMock
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.binary"] = MagicMock()

from backend.main import app


def generate():
    """Generate OpenAPI specs and write them to docs/."""
    openapi_schema = app.openapi()

    output_dir = _REPO_ROOT / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "openapi.json"
    yaml_path = output_dir / "openapi.yaml"

    with open(json_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    with open(yaml_path, "w") as f:
        yaml.dump(openapi_schema, f, sort_keys=False)

    print(f"Generated OpenAPI specs in {output_dir}")


if __name__ == "__main__":
    generate()
