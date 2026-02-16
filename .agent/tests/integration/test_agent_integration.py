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

import os
import shutil
import subprocess

import pytest

# Path to the real repository root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def get_venv_env():
    """Get environment with venv bin in PATH."""
    import sys
    env = os.environ.copy()
    venv_bin = os.path.dirname(sys.executable)
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
    return env

@pytest.fixture
def agent_sandbox(tmp_path):
    """
    Creates a sandbox environment with a copy of .agent and a initialized git repo.
    Returns the path to the agent executable and the sandbox cwd.
    """
    # Initialize git repo in tmp_path
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=tmp_path, check=True, capture_output=True)
    
    # Copy .agent directory — exclude heavy dirs to prevent memory pressure
    src_agent = os.path.join(REPO_ROOT, ".agent")
    dest_agent = tmp_path / ".agent"
    
    def _ignore_heavy_dirs(directory, contents):
        """Exclude __pycache__, .venv, node_modules, and .git to reduce memory footprint."""
        return {c for c in contents if c in ('__pycache__', '.venv', 'node_modules', '.git', '.pytest_cache')}
    
    shutil.copytree(src_agent, dest_agent, ignore=_ignore_heavy_dirs)
    
    # Executable path
    agent_bin = dest_agent / "bin" / "agent"
    
    # Make sure it's executable
    os.chmod(agent_bin, 0o755)

    # Create a wrapper script/function to run agent with new env
    # OR just return the bin path and let tests assume consistent environment?
    # Actually, we need to enforce AGENT_ROOT in the ENTIRE test session if possible,
    # or just set it in the environment that runs the agent.
    # The tests use `subprocess.run([bin, ...])`. We should wrap this or export variable.
    # Since we can't easily wrap the binary return, let's set it in os.environ for the duration?
    # No, that affects the test process.
    # Better: The tests should pass `env={...}`.
    # But looking at usage: `subprocess.run([agent_bin, ...], cwd=tmp_path)`
    # It inherits env. So setting os.environ["AGENT_ROOT"] = str(tmp_path) works!
    
    os.environ["AGENT_ROOT"] = str(tmp_path)
    
    # REMOVE Secrets to avoid interaction prompts needing passwords
    # This ensures the agent runs in a "fresh" state for these tests
    secrets_db = dest_agent / "secrets.db"
    secrets_dir = dest_agent / "secrets"
    if secrets_db.exists():
        secrets_db.unlink()
    if secrets_dir.exists():
        shutil.rmtree(secrets_dir)
    
    yield str(agent_bin), tmp_path
    
    # Teardown
    del os.environ["AGENT_ROOT"]

def test_agent_help(agent_sandbox):
    """Test standard help output."""
    agent_bin, _ = agent_sandbox
    result = subprocess.run([agent_bin, "help"], capture_output=True, text=True, env=get_venv_env(), timeout=30)
    # Depending on checking behavior, if no secrets, it might just print help. 
    # If it fails due to missing deps (not installed in sandbox venv context?), we check return code.
    # But usually help should always work.
    assert result.returncode == 0
    assert "A CLI for managing and interacting with the AI agent" in result.stdout
    assert "preflight" in result.stdout
    assert "pr" in result.stdout

def test_new_story_interactive(agent_sandbox):
    """Test interactive new-story creation."""
    agent_bin, cwd = agent_sandbox
    
    # Run with input to set title
    proc = subprocess.Popen(
        [agent_bin, "new-story", "INFRA-999"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=get_venv_env()
    )
    stdout, stderr = proc.communicate(input="Test Story Title\n", timeout=30)
    
    assert proc.returncode == 0
    assert "Created story" in stdout
    
    # Verify file exists
    story_path = cwd / ".agent" / "cache" / "stories" / "INFRA" / "INFRA-999-test-story-title.md"
    assert story_path.exists()
    
    # Verify content
    content = story_path.read_text()
    assert "# INFRA-999: Test Story Title" in content

def test_new_story_auto_id(agent_sandbox):
    """Test new-story with auto-ID generation."""
    agent_bin, cwd = agent_sandbox
    
    # Input: 1 (INFRA), Title
    inputs = "1\nAuto ID Title\n"
    
    proc = subprocess.Popen(
        [agent_bin, "new-story"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=get_venv_env()
    )
    stdout, stderr = proc.communicate(input=inputs, timeout=30)
    
    assert proc.returncode == 0
    assert "Auto-assigning ID: INFRA-" in stdout
    
    # Helper to find the created file since we don't know the exact ID
    stories_dir = cwd / ".agent" / "cache" / "stories" / "INFRA"
    files = list(stories_dir.glob("INFRA-*-auto-id-title.md"))
    assert len(files) == 1
    assert files[0].exists()

def test_new_plan(agent_sandbox):
    """Test new-plan creation."""
    agent_bin, cwd = agent_sandbox
    
    proc = subprocess.Popen(
        [agent_bin, "new-plan", "WEB-123"],  # explicit ID
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=get_venv_env()
    )
    stdout, stderr = proc.communicate(input="My Plan\n", timeout=30)
    assert proc.returncode == 0
    
    plan_path = cwd / ".agent" / "cache" / "plans" / "WEB" / "WEB-123-my-plan.md"
    assert plan_path.exists()

def test_new_adr(agent_sandbox):
    """Test new-adr creation."""
    agent_bin, cwd = agent_sandbox
    
    proc = subprocess.Popen(
        [agent_bin, "new-adr", "ADR-005"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=get_venv_env()
    )
    stdout, stderr = proc.communicate(input="Architecture Decision\n", timeout=30)
    assert proc.returncode == 0
    
    adr_path = cwd / ".agent" / "adrs" / "ADR-005-architecture-decision.md"
    assert adr_path.exists()

def test_validate_story_success(agent_sandbox):
    """Test validating a valid story."""
    agent_bin, cwd = agent_sandbox
    
    # First create a valid story
    story_id = "MOBILE-777"
    subprocess.run([agent_bin, "new-story", story_id], input="Valid Story\n", text=True, cwd=cwd, check=True, capture_output=True, env=get_venv_env(), timeout=30)
    
    # Run validate
    result = subprocess.run([agent_bin, "validate-story", story_id], cwd=cwd, capture_output=True, text=True, env=get_venv_env(), timeout=30)
    assert result.returncode == 0
    assert f"Story schema validation passed for {story_id}" in result.stdout

def test_pr_help_check(agent_sandbox):
    """Verify 'agent pr' command loads and displays help (regression test for missing cmd_pr)."""
    agent_bin, cwd = agent_sandbox
    result = subprocess.run([agent_bin, "pr", "--help"], capture_output=True, text=True, cwd=cwd, env=get_venv_env(), timeout=30)
    assert result.returncode == 0
    assert "Open a GitHub Pull Request" in result.stdout
    assert "--story" in result.stdout

def test_agent_no_args(agent_sandbox):
    """Test that running agent without arguments displays help and does not crash."""
    agent_bin, cwd = agent_sandbox
    result = subprocess.run([agent_bin], capture_output=True, text=True, cwd=cwd, env=get_venv_env(), timeout=30)
    assert result.returncode == 0
    assert "Usage: agent [COMMAND]" in result.stdout or "Usage: python -m agent.main" in result.stdout
    assert "A CLI for managing and interacting with the AI agent" in result.stdout

def test_agent_nested_help(agent_sandbox):
    """Test 'agent <cmd> help' syntax translation."""
    agent_bin, cwd = agent_sandbox
    result = subprocess.run([agent_bin, "preflight", "help"], capture_output=True, text=True, cwd=cwd, env=get_venv_env(), timeout=30)
    assert result.returncode == 0
    assert "Run preflight checks" in result.stdout or "Run governance preflight checks" in result.stdout

