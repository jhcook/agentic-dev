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

"""Utility to establish test baselines and verify discovery delta post-migration."""

import subprocess
import json
import os
import sys
from datetime import datetime

def run_pytest_collection():
    """Collects tests via pytest and returns count of items discovered."""
    # Query pytest collection without executing tests to establish discovery count
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True
    )
    for line in result.stdout.splitlines():
        if "collected" in line and "items" in line:
            try:
                # Standard pytest output: "collected X items"
                return int(line.split(' ')[1])
            except (IndexError, ValueError):
                continue
    return 0

def get_orphaned_src_tests():
    """Identifies any test directories remaining inside the src/ hierarchy."""
    orphans = []
    for root, dirs, _ in os.walk(".agent/src"):
        if "tests" in dirs:
            orphans.append(os.path.join(root, "tests"))
    return orphans

def main():
    """Main execution for observability metrics."""
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tests_discovered": run_pytest_collection(),
        "orphaned_src_directories": get_orphaned_src_tests(),
        "discovery_path": ".agent/tests/",
        "status": "PENDING"
    }
    
    # Determine status based on architectural standards
    if metrics["orphaned_src_directories"]:
        metrics["status"] = "FAIL: Colocated tests detected in src/"
    else:
        metrics["status"] = "PASS"
        
    print(json.dumps(metrics, indent=2))
    
    if metrics["orphaned_src_directories"]:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
