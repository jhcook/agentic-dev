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

"""Tests for implementation error handling and guard violations."""

import pytest
from agent.core.implement.guards import (
    check_file_size_guard,
    FileSizeGuardViolation,
    FILE_SIZE_GUARD_THRESHOLD,
    apply_change_to_file
)

def test_file_size_guard_violation(tmp_path):
    """Verify that exceeding the LOC threshold raises FileSizeGuardViolation with a hint."""
    target_file = tmp_path / "large_file.py"
    target_file.write_text("existing content\n" * 5)
    
    # Create content exceeding threshold
    large_content = "\n".join(["print('test')"] * (FILE_SIZE_GUARD_THRESHOLD + 1))
    
    with pytest.raises(FileSizeGuardViolation) as excinfo:
        apply_change_to_file(str(target_file), large_content, yes=True)
    
    assert "already exists and new content is" in str(excinfo.value)
    assert "incremental changes" in str(excinfo.value)

def test_file_size_guard_new_file_allowed(tmp_path):
    """Verify that a non-existent file is allowed even if it is large (it's not an overwrite)."""
    target_file = tmp_path / "new_large_file.py"
    large_content = "\n".join(["print('test')"] * (FILE_SIZE_GUARD_THRESHOLD + 1))
    
    # Should NOT raise because path.exists() is False
    result = apply_change_to_file(str(target_file), large_content, yes=True)
    assert result is True