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

# Licensed under the Apache License, Version 2.0 (the "License");

import subprocess
from pathlib import Path
from agent.core.logger import get_logger
from agent.core.check.models import SmartTestSelectionResult
from opentelemetry import trace

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

def run_smart_test_selection(base: str | None, skip_tests: bool, interactive: bool, ignore_tests: bool) -> SmartTestSelectionResult:
    """Implement Smart Test Selection.
    
    Selects test commands based on the set of modified files in the given git base comparing
    to HEAD. Understands the boundary between Python tests and Javascript/TypeScript tests 
    (NPM in web/mobile partitions) and delegates to the appropriate test runners.
    
    Args:
        base: The base git branch to diff against (e.g. 'main').
        skip_tests: If True, skips testing immediately and returns success.
        interactive: If True, runs process interactions inline.
        ignore_tests: If True, allows preflight to succeed even if tests fail.
        
    Returns:
        SmartTestSelectionResult with the test commands to execute.
    """
    with tracer.start_as_current_span("run_smart_test_selection"):
        result: SmartTestSelectionResult = {
            "passed": True,
            "skipped": skip_tests,
            "test_commands": [],
            "ignored": ignore_tests,
            "error": None
        }

    if skip_tests:
        return result

    # Identify changed files
    if base:
        cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        
    try:
        diff_res = subprocess.run(cmd, capture_output=True, text=True)
        files = [Path(f) for f in diff_res.stdout.strip().splitlines() if f]
    except Exception as e:
        logger.error("Error finding changed files", extra={"error": str(e)})
        result["error"] = f"Error finding changed files: {e}"
        result["passed"] = False
        return result

    # Analyze Dependencies
    from agent.core.dependency_analyzer import DependencyAnalyzer
    analyzer = DependencyAnalyzer(Path.cwd())
    
    backend_changes = [f for f in files if str(f).startswith("backend/") or str(f).startswith(".agent/src/backend/")]
    mobile_changes = [f for f in files if str(f).startswith("mobile/")]
    web_changes = [f for f in files if str(f).startswith("web/")]
    
    root_py_changes = []
    for f in files:
        if f.suffix == ".py":
            is_backend = str(f).startswith("backend/") or str(f).startswith(".agent/src/backend/")
            if not is_backend:
                root_py_changes.append(f)

    # --- .agent/ Framework Strategy ---
    # When .agent/ files are modified, run the framework's own test suite
    # using the same test_commands config that `agent implement` uses.
    # This closes the regression gap where the generic rglob filter below
    # excludes .agent/ tests from smart selection.
    agent_changes = [f for f in files if str(f).startswith(".agent/")]
    if agent_changes:
        try:
            import yaml as _yaml
            agent_cfg_path = Path(".agent/etc/agent.yaml")
            if agent_cfg_path.exists():
                agent_cfg = _yaml.safe_load(agent_cfg_path.read_text())
                test_cmds = agent_cfg.get("agent", {}).get("test_commands", {})
                agent_test_cmd = None
                if isinstance(test_cmds, dict):
                    agent_test_cmd = test_cmds.get(".agent/")
                elif isinstance(test_cmds, str):
                    agent_test_cmd = test_cmds
                if agent_test_cmd:
                    result["test_commands"].append({
                        "name": "Agent Framework Tests",
                        "cmd": ["bash", "-c", agent_test_cmd],
                        "cwd": Path.cwd()
                    })
                    logger.info(
                        "smart_test_selection agent_framework_tests enabled, "
                        "changed_agent_files=%d", len(agent_changes)
                    )
        except Exception as e:
            logger.warning("Could not load agent.yaml test config: %s", e)

    # --- Python / Backend Strategy ---
    if backend_changes or root_py_changes:
        all_test_files = list(Path.cwd().rglob("test_*.py")) + list(Path.cwd().rglob("*_test.py"))
        filtered_tests = []
        for f in all_test_files:
            rel_path = f.relative_to(Path.cwd())
            parts = rel_path.parts
            
            if "node_modules" in parts or ".venv" in parts or "venv" in parts:
                continue
            # .agent/ tests are handled by the dedicated strategy above
            if ".agent" in parts:
                continue
                
            filtered_tests.append(rel_path)
        
        all_test_files = filtered_tests
        relevant_tests = set()
        changed_set = set(files)
        
        for test_file in all_test_files:
            deps = analyzer.get_file_dependencies(test_file)
            if changed_set.intersection(deps):
                relevant_tests.add(test_file)
            if test_file in changed_set:
                relevant_tests.add(test_file)
        
        pytest_args = ["-m", "pytest", "-v", "--ignore=.agent"]
        
        if relevant_tests:
            if len(relevant_tests) < 50:
                pytest_args.extend([str(t) for t in relevant_tests])
            else:
                if backend_changes: pytest_args.append("backend")
                if root_py_changes: pytest_args.append(".")
        else:
            pytest_args = None

        if pytest_args:
             root_venv_python = Path(".venv/bin/python")
             import sys
             if root_venv_python.exists():
                  python_exe = str(root_venv_python)
             else:
                  python_exe = sys.executable
            
             result["test_commands"].append({
                 "name": "Python Tests",
                 "cmd": [python_exe] + pytest_args,
                 "cwd": Path.cwd()
             })

    # --- Mobile Strategy (NPM) ---
    if mobile_changes:
        mobile_root = Path("mobile")
        pkg_json = mobile_root / "package.json"
        node_modules = mobile_root / "node_modules"
        if pkg_json.exists() and node_modules.exists():
            import json
            scripts = json.loads(pkg_json.read_text()).get("scripts", {})
            
            if "lint" in scripts:
                result["test_commands"].append({
                    "name": "Mobile Lint",
                    "cmd": ["npm", "run", "lint"],
                    "cwd": mobile_root
                })
            if "test" in scripts:
                result["test_commands"].append({
                    "name": "Mobile Tests",
                    "cmd": ["npm", "test"],
                    "cwd": mobile_root
                })

    # --- Web Strategy (NPM) ---
    if web_changes:
        web_root = Path("web")
        pkg_json = web_root / "package.json"
        node_modules = web_root / "node_modules"
        if pkg_json.exists() and node_modules.exists():
            import json
            scripts = json.loads(pkg_json.read_text()).get("scripts", {})
            
            if "lint" in scripts:
                result["test_commands"].append({
                    "name": "Web Lint",
                    "cmd": ["npm", "run", "lint"],
                    "cwd": web_root
                })
                if "test" in scripts:
                    result["test_commands"].append({
                        "name": "Web Tests",
                        "cmd": ["npm", "test"],
                        "cwd": web_root
                    })
    
    return result