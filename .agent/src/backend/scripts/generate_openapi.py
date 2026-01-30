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

import json
import sys
import yaml
from pathlib import Path

# Add src to path to import backend
sys.path.append(str(Path(__file__).parent.parent.parent))

from unittest.mock import MagicMock
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.binary"] = MagicMock()

from backend.main import app

def generate():
    openapi_schema = app.openapi()
    
    # Project root (relative to this script: .agent/src/backend/scripts -> .agent/docs ? No, docs is in .agent/docs)
    # Actually commonly docs/ usually refers to project root docs if it exists, or .agent/docs
    # Let's target .agent/docs based on list_dir output intent
    
    output_dir = Path(__file__).parents[4] / "docs"
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
