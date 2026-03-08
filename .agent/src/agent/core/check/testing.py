# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0 (the "License");

import subprocess
from pathlib import Path
from rich.console import Console
from agent.core.logger import get_logger

logger = get_logger(__name__)

import typer

def run_smart_test_selection(console: Console, base: str | None, skip_tests: bool, interactive: bool, ignore_tests: bool, json_report: dict) -> bool:
    """Implement Smart Test Selection and execution."""
    if skip_tests:
        console.print("[yellow]⏩ Skipping automated tests (--skip-tests passed).[/yellow]")
        return True

    console.print("[bold blue]🧪 Implementing Smart Test Selection...[/bold blue]")
    
    # Identify changed files
    if base:
        cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        files = [Path(f) for f in result.stdout.strip().splitlines() if f]
    except Exception as e:
        logger.error("Error finding changed files", extra={"error": str(e)})
        console.print(f"[bold red]❌ Error finding changed files: {e}[/bold red]")
        files = []

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
    
    test_commands = []
    
    # --- Python / Backend Strategy ---
    if backend_changes or root_py_changes:
        console.print("[dim]🐍 Analyzing Python dependencies...[/dim]")
        
        all_test_files = list(Path.cwd().rglob("test_*.py")) + list(Path.cwd().rglob("*_test.py"))
        filtered_tests = []
        for f in all_test_files:
            rel_path = f.relative_to(Path.cwd())
            parts = rel_path.parts
            
            if "node_modules" in parts or ".venv" in parts or "venv" in parts:
                continue
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
            console.print(f"[green]🎯 Found {len(relevant_tests)} relevant test(s).[/green]")
            for rt in relevant_tests:
                console.print(f"  - {rt}")
            if len(relevant_tests) < 50:
                pytest_args.extend([str(t) for t in relevant_tests])
            else:
                console.print("[yellow]Files list too long, falling back to directory discovery.[/yellow]")
                if backend_changes: pytest_args.append("backend")
                if root_py_changes: pytest_args.append(".")
        else:
            console.print("[dim]ℹ️  No test files depend on the changed code — skipping Python tests.[/dim]")
            pytest_args = None

        if pytest_args:
             root_venv_python = Path(".venv/bin/python")
             import sys
             if root_venv_python.exists():
                  python_exe = str(root_venv_python)
             else:
                  python_exe = sys.executable
            
             test_commands.append({
                 "name": "Python Tests",
                 "cmd": [python_exe] + pytest_args,
                 "cwd": Path.cwd()
             })

    # --- Mobile Strategy (NPM) ---
    if mobile_changes:
        console.print("[dim]📱 Detecting Mobile (React Native) changes...[/dim]")
        mobile_root = Path("mobile")
        pkg_json = mobile_root / "package.json"
        node_modules = mobile_root / "node_modules"
        if pkg_json.exists() and node_modules.exists():
            import json
            scripts = json.loads(pkg_json.read_text()).get("scripts", {})
            
            if "lint" in scripts:
                test_commands.append({
                    "name": "Mobile Lint",
                    "cmd": ["npm", "run", "lint"],
                    "cwd": mobile_root
                })
            if "test" in scripts:
                test_commands.append({
                    "name": "Mobile Tests",
                    "cmd": ["npm", "test"],
                    "cwd": mobile_root
                })
        elif pkg_json.exists():
            console.print("[dim]  ⏭️  Skipping mobile lint/tests (node_modules not installed — handled by mobile-ci workflow)[/dim]")

    # --- Web Strategy (NPM) ---
    if web_changes:
        console.print("[dim]🌐 Detecting Web (Next.js) changes...[/dim]")
        web_root = Path("web")
        pkg_json = web_root / "package.json"
        node_modules = web_root / "node_modules"
        if pkg_json.exists() and node_modules.exists():
            import json
            scripts = json.loads(pkg_json.read_text()).get("scripts", {})
            
            if "lint" in scripts:
                test_commands.append({
                    "name": "Web Lint",
                    "cmd": ["npm", "run", "lint"],
                    "cwd": web_root
                })
            if "test" in scripts:
                test_commands.append({
                    "name": "Web Tests",
                    "cmd": ["npm", "test"],
                    "cwd": web_root
                })
        elif pkg_json.exists():
            console.print("[dim]  ⏭️  Skipping web lint/tests (node_modules not installed — handled by web CI workflow)[/dim]")

    # --- EXECUTE CMDS ---
    tests_passed = True
    
    if not test_commands:
         console.print("[green]✅ No relevant tests to run based on changed files.[/green]")
         json_report["overall_verdict"] = "PASS"
    
    for task in test_commands:
        console.print(f"[bold cyan]🏃 Running: {task['name']}[/bold cyan]")
        try:
            process = subprocess.Popen(
                task['cmd'],
                cwd=task['cwd'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            captured_output = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    console.print(line, end="", markup=False)
                    captured_output.append(line)
                    
            rc = process.poll()
            from types import SimpleNamespace
            res = SimpleNamespace(returncode=rc, stdout="".join(captured_output), stderr="")

            if res.returncode == 5:
                console.print(f"[yellow]⚠️  {task['name']}: No tests collected (skipped)[/yellow]")
            elif res.returncode != 0:
                console.print(f"[bold red]❌ {task['name']} FAILED[/bold red]")
                tests_passed = False
                
                if interactive:
                    console.print("\n[bold yellow]Agentic Repair is currently disabled for security compliance.[/bold yellow]")

                if not tests_passed and not ignore_tests:
                    break
            else:
                console.print(f"[green]✅ {task['name']} PASSED[/green]")
        except FileNotFoundError as e:
             logger.error("Command not found", extra={"error": str(e), "command": task['cmd'][0]})
             console.print(f"[red]❌ Command not found: {task['cmd'][0]}[/red]")
             tests_passed = False

    if not tests_passed:
        msg = "Automated tests failed."
        if ignore_tests:
            console.print(f"[yellow]⚠️  {msg} (Ignored by --ignore-tests)[/yellow]")
            return False
        else:
            console.print(f"[bold red]❌ {msg} Preflight ABORTED.[/bold red]")
            json_report["overall_verdict"] = "BLOCK"
            json_report["error"] = msg
            return False
    elif test_commands:
        console.print("[bold green]✅ All tests passed.[/bold green]")
        json_report["overall_verdict"] = "PASS"
    return True
