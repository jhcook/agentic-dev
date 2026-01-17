import pytest
from click.testing import CliRunner
from ..src.agent.cli import cli

runner = CliRunner()

def test_valid_provider():
    result = runner.invoke(cli, ["implement", "--story", "a feature", "--provider", "openai"])
    assert result.exit_code == 0
    assert "Executing 'implement' with provider: openai." in result.output

def test_invalid_provider():
    result = runner.invoke(cli, ["implement", "--story", "a feature", "--provider", "foobar"])
    assert result.exit_code != 0
    assert "Invalid provider 'foobar'" in result.output

def test_unconfigured_provider():
    result = runner.invoke(cli, ["pr", "--provider", "gemini"])
    assert result.exit_code != 0
    assert "Provider 'gemini' is not configured" in result.output

def test_default_provider():
    result = runner.invoke(cli, ["new-runbook"])
    assert result.exit_code == 0
    assert "Executing 'new_runbook' with provider: gh." in result.output