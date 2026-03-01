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
import logging
from pathlib import Path
import pytest

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("check_notion_schema")

ROOT_DIR = Path(__file__).resolve().parents[3] # .agent/tests/unit -> .agent/tests -> .agent -> root
SCHEMA_FILE = ROOT_DIR / ".agent" / "etc" / "notion_schema.json"

REQUIRED_DB_KEYS = ["Stories", "Plans", "ADRs"]
VALID_PROPERTY_TYPES = [
    "title", "rich_text", "number", "select", "multi_select", 
    "date", "people", "files", "checkbox", "url", "email", 
    "phone_number", "formula", "relation", "rollup", 
    "created_time", "created_by", "last_edited_time", "last_edited_by",
    "status" 
]

def test_validate_notion_schema():
    """Validates the static notion_schema.json file."""
    if not SCHEMA_FILE.exists():
        pytest.fail(f"Schema file missing: {SCHEMA_FILE}")

    try:
        with open(SCHEMA_FILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON: {e}")

    databases = data.get("databases")
    assert databases, "Missing 'databases' key."

    # Check for required databases
    missing = [key for key in REQUIRED_DB_KEYS if key not in databases]
    assert not missing, f"Missing required databases: {missing}"

    # Validate structure
    for key, db_def in databases.items():
        assert "title" in db_def, f"Database '{key}' missing 'title'."
        
        properties = db_def.get("properties")
        assert properties, f"Database '{key}' missing 'properties'."
            
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type")
            assert prop_type, f"Property '{prop_name}' in '{key}' missing 'type'."
            
            assert prop_type in VALID_PROPERTY_TYPES, f"Property '{prop_name}' in '{key}' has invalid type '{prop_type}'."
                
            # specific checks
            if prop_type == "select" or prop_type == "multi_select":
                assert "options" in prop_def, f"Select property '{prop_name}' in '{key}' missing 'options'."
