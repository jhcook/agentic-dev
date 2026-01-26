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

from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()

def test_version_flag_long():
    """Test --version works."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Agent CLI" in result.stdout

def test_version_flag_short_removed():
    """Test -v is NO LONGER version."""
    # It should interpret -v as an unknown option or fail if no command matches
    result = runner.invoke(app, ["-v"])
    # Typer/Click will say "no such option: -v" and exit with 2 (Usage error)
    assert result.exit_code != 0
    # result.stdout might be empty if error is on stderr. result.output captures both for CliRunner.
    # Check that it didn't print the version string, which would imply success.
    assert "Agent CLI" not in result.stdout

def test_new_story_options():
    """Test new-story help and options."""
    result = runner.invoke(app, ["new-story", "--help"])
    assert result.exit_code == 0
    assert "--help" in result.stdout

def test_pr_options():
    """Test pr command options."""
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0
    assert "--story" in result.stdout
    assert "--web" in result.stdout
    assert "--draft" in result.stdout

def test_preflight_options():
    """Test preflight command options."""
    result = runner.invoke(app, ["preflight", "--help"])
    assert result.exit_code == 0
    assert "--story" in result.stdout
    assert "--ai" in result.stdout
    assert "--base" in result.stdout

def test_list_options():
    """Test list commands options."""
    for cmd in ["list-stories", "list-plans", "list-runbooks"]:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0

def test_validate_story_options():
    """Test validate-story options."""
    result = runner.invoke(app, ["validate-story", "--help"])
    assert result.exit_code == 0

def test_commit_options():
    """Test commit options."""
    result = runner.invoke(app, ["commit", "--help"])
    assert result.exit_code == 0
    assert "--story" in result.stdout
    assert "--runbook" in result.stdout

def test_plan_help():
    result = runner.invoke(app, ["new-plan", "--help"])
    assert result.exit_code == 0
    assert "Create a new implementation plan" in result.stdout

def test_implement_help():
    result = runner.invoke(app, ["implement", "--help"])
    assert result.exit_code == 0
    # "Generate code" might vary based on Typer help generation, checking command name presence or part of docstring
    assert "implement" in result.stdout 

def test_new_runbook_help():
    result = runner.invoke(app, ["new-runbook", "--help"])
    assert result.exit_code == 0
    assert "runbook" in result.stdout

def test_match_story_help():
    result = runner.invoke(app, ["match-story", "--help"])
    assert result.exit_code == 0
    assert "match" in result.stdout
