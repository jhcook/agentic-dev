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

"""Verification utility for INFRA-144 tool registration."""

import importlib
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("INFRA-144-Verify")

def main():
    """Verify that the new tool modules are discoverable and contain expected entry points."""
    logger.info("Starting INFRA-144 verification...")
    
    # Mapping of domains to their core required interfaces as per AC-1 through AC-4
    expected = {
        "web": ["fetch_url", "read_docs"],
        "testing": ["run_tests", "run_single_test", "coverage_report"],
        "deps": ["add_dependency", "audit_dependencies", "list_outdated"],
        "context": ["checkpoint", "rollback", "summarize_changes"]
    }
    
    errors = 0
    for module_name, functions in expected.items():
        full_path = f"agent.tools.{module_name}"
        try:
            mod = importlib.import_module(full_path)
            logger.info(f"✓ Successfully imported {full_path}")
            for func in functions:
                if hasattr(mod, func):
                    logger.info(f"  ✓ Function '{func}' found.")
                else:
                    logger.error(f"  ✗ Function '{func}' NOT found in {full_path}.")
                    errors += 1
        except ImportError as e:
            logger.error(f"✗ Critical failure: Could not import {full_path}: {e}")
            errors += 1
            
    if errors == 0:
        logger.info("All INFRA-144 tools are correctly registered and available.")
        sys.exit(0)
    else:
        logger.error(f"Verification failed with {errors} errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
