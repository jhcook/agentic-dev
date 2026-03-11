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

import pytest
import os

@pytest.fixture(autouse=True)
def set_terminal_width():
    """Force rich/typer to use a wide terminal so output assertions don't break due to word wrapping."""
    os.environ["COLUMNS"] = "1000"
    yield
    os.environ.pop("COLUMNS", None)


@pytest.fixture
def run_cli_command():
    # Placeholder for Typer CliRunner logic if needed
    from typer.testing import CliRunner
    return CliRunner()
@pytest.fixture(autouse=True)
def isolate_secrets_dir(tmp_path, monkeypatch):
    """Ensure no tests touch the live .agent/secrets directory by default."""
    import agent.core.secrets
    secrets_dir = tmp_path / "secrets"
    # Overwrite the default constructor
    original_init = agent.core.secrets.SecretManager.__init__
    
    def mock_init(self, dir_path=None):
        original_init(self, secrets_dir)
        
    monkeypatch.setattr(agent.core.secrets.SecretManager, "__init__", mock_init)
    
    # Reset singleton to force recreation using the mocked init
    monkeypatch.setattr(agent.core.secrets, "_secret_manager", None)
