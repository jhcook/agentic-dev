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

"""
Rollback verification script for INFRA-173.
Ensures that the docstring validator has returned to strict rejection mode.
"""
import sys

try:
    from agent.core.governance.validation import DocstringValidator
except ImportError:
    print("Error: Could not find DocstringValidator. Check source tree.")
    sys.exit(1)

def main():
    """Main verification routine."""
    validator = DocstringValidator()
    # test_*.py files were bypassed/downgraded in INFRA-173.
    # In strict mode, they should trigger a rejection if docstrings are missing.
    test_filename = "test_rollback_verification.py"
    test_content = "def test_logic(): pass"
    
    # Attempt to validate content that INFRA-173 would allow
    result = validator.validate(test_filename, test_content)
    
    # Check if status is back to 'fail'
    status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    
    if status == "fail":
        print("Rollback Verified: Strict docstring enforcement is active.")
        sys.exit(0)
    else:
        print("Rollback Check Failed: System is still in warning/bypass mode.")
        sys.exit(1)

if __name__ == "__main__":
    main()
