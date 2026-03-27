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

from unittest.mock import MagicMock, patch
from pathlib import Path
from implement.verbatim_apply import VerbatimApplier

@patch("implement.verbatim_apply.write_file")
@patch("implement.verbatim_apply.DocstringValidator")
def test_apply_writes_on_warning(mock_validator_cls: MagicMock, mock_write: MagicMock) -> None:
    """Verify that files with WARNING status are still written to the filesystem.
    
    Ensures work is not discarded even if linting/doc gaps exist.
    """
    mock_validator = mock_validator_cls.return_value
    mock_validator.validate.return_value = MagicMock(status="WARNING", message="Doc gap")
    
    applier = VerbatimApplier()
    success, status = applier.apply(Path("token_counter.py"), "content")
    
    assert success is True
    assert status == "WARNING"
    mock_write.assert_called_once()
