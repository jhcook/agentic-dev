
import pytest
import yaml
from typer.testing import CliRunner

from agent.core.config import config
from agent.main import app

runner = CliRunner()

@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """
    Redirect config directories to tmp_path.
    """
    etc_dir = tmp_path / "etc"
    etc_dir.mkdir()
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    
    # router.yaml
    router_yaml = etc_dir / "router.yaml"
    router_data = {
        "models": {
            "gpt-4o": {"tier": "advanced"}
        }
    }
    with open(router_yaml, "w") as f:
        yaml.dump(router_data, f)
        
    # agents.yaml (second file)
    agents_yaml = etc_dir / "agents.yaml"
    agents_data = {
        "team": [{"role": "architect", "name": "System Architect"}]
    }
    with open(agents_yaml, "w") as f:
        yaml.dump(agents_data, f)
        
    monkeypatch.setattr(config, "etc_dir", etc_dir)
    monkeypatch.setattr(config, "backups_dir", backups_dir)
    
    return etc_dir

def test_config_get_default(mock_config):
    # Should default to router.yaml
    result = runner.invoke(app, ["config", "get", "models.gpt-4o.tier"])
    assert result.exit_code == 0
    assert "advanced" in result.stdout

def test_config_get_prefix_routing(mock_config):
    # Should route to agents.yaml
    result = runner.invoke(app, ["config", "get", "agents.team.0.role"])
    assert result.exit_code == 0
    assert "architect" in result.stdout

def test_config_set_prefix_routing(mock_config):
    # Should route to agents.yaml
    result = runner.invoke(app, ["config", "set", "agents.team.0.name", "New Name"])
    assert result.exit_code == 0
    assert "Successfully updated 'team.0.name' in agents.yaml" in result.stdout
    
    with open(mock_config / "agents.yaml") as f:
        data = yaml.safe_load(f)
    assert data["team"][0]["name"] == "New Name"

def test_config_list_all(mock_config):
    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "### router.yaml ###" in result.stdout
    assert "### agents.yaml ###" in result.stdout
    assert "gpt-4o" in result.stdout
    assert "System Architect" in result.stdout

def test_config_explicit_file(mock_config):
    result = runner.invoke(app, ["config", "list", "--file", "agents.yaml"])
    assert result.exit_code == 0
    assert "### agents.yaml ###" in result.stdout
    assert "### router.yaml ###" not in result.stdout

def test_config_atomic_backup(mock_config):
    result = runner.invoke(app, ["config", "set", "models.gpt-4o.tier", "light"])
    assert result.exit_code == 0
    backups = list(config.backups_dir.glob("router_*.yaml"))
    assert len(backups) == 1

def test_config_methods_unit():
    data = {"a": 1}
    assert config.get_value(data, "a") == 1
    config.set_value(data, "b", 2)
    assert data["b"] == 2
