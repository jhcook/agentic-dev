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

import re
import subprocess
import time
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from agent.core.logger import get_logger
from agent.core.config import config
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.ai.prompts import generate_impact_prompt

console = Console()
logger = get_logger(__name__)

def run_ui_tests(
    story_id: Optional[str] = typer.Argument(None, help="The ID of the story (for context/logging)."),
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter test flows by keyword.")
):
    """
    Run UI journey tests using Maestro.
    """
    import shutil
    import subprocess
    import time
    from pathlib import Path
    
    console.print("[bold blue]📱 Initiating UI Test Run (Maestro)[/bold blue]")
    logger.info("Starting run_ui_tests", extra={"story_id": story_id, "filter": filter})

    # 2. Check Prerequisites
    maestro_path = shutil.which("maestro")
    if not maestro_path:
        msg = "Maestro CLI is not installed or not in PATH."
        logger.error(msg)
        console.print(f"[bold red]❌ {msg}[/bold red]")
        console.print("Please install Maestro: https://maestro.mobile.dev/")
        raise typer.Exit(code=1)

    # 3. Find Test Flows
    search_paths = [Path("tests/ui"), Path(".maestro")]
    test_flows = []
    
    for path in search_paths:
        if path.exists() and path.is_dir():
            found = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
            test_flows.extend(found)
            
    if not test_flows:
        msg = f"No .yaml/.yml test flows found in {', '.join([str(p) for p in search_paths])}."
        logger.info(msg)
        console.print(f"[yellow]⚠️  {msg}[/yellow]")
        raise typer.Exit(code=0)

    # 4. Filter Flows
    if filter:
        test_flows = [f for f in test_flows if filter in f.name]
        if not test_flows:
            msg = f"No test flows match filter '{filter}'."
            logger.info(msg)
            console.print(f"[yellow]⚠️  {msg}[/yellow]")
            raise typer.Exit(code=0)

    logger.info("Found test flows", extra={"count": len(test_flows), "flows": [f.name for f in test_flows]})
    console.print(f"Found {len(test_flows)} test flows.")

    # 5. Execute Flows
    failed_flows = []
    passed_flows = []

    for flow in test_flows:
        console.print(f"\n[bold cyan]🏃 Running: {flow.name}[/bold cyan]")
        logger.info("Running flow", extra={"flow": str(flow)})
        
        start_time = time.time()
        try:
            # We stream output to console and also capture it? 
            # Maestro output is pretty rich, let's let it stream to stdout 
            # but assume failure if return code != 0
            
            # Using subprocess.run to allow streaming if we didn't capture_output, 
            # but for log capture we might need to capture.
            # Let's verify compatibility. Simple run:
            
            result = subprocess.run(
                [maestro_path, "test", str(flow)],
                check=False  # We handle code manually
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                console.print(f"[green]✅ PASSED ({duration:.2f}s)[/green]")
                logger.info("Flow passed", extra={"flow": flow.name, "duration": duration})
                passed_flows.append(flow.name)
            else:
                console.print(f"[red]❌ FAILED ({duration:.2f}s)[/red]")
                logger.warning("Flow failed", extra={"flow": flow.name, "duration": duration, "exit_code": result.returncode})
                failed_flows.append(flow.name)
                
        except Exception as e:
            console.print(f"[red]❌ Error executing flow {flow.name}: {e}[/red]")
            logger.error("Exception executing flow", extra={"flow": flow.name, "error": str(e)})
            failed_flows.append(flow.name)

    # 6. Summary
    console.print("\n[bold]Test Summary[/bold]")
    console.print(f"Total: {len(test_flows)}")
    console.print(f"[green]Passed: {len(passed_flows)}[/green]")
    
    if failed_flows:
        console.print(f"[red]Failed: {len(failed_flows)}[/red]")
        for f in failed_flows:
             console.print(f" - {f}")
        
        logger.error("Run FAILED", extra={"failed_flows": failed_flows})
        raise typer.Exit(code=1)
    else:
        logger.info("Run PASSED")
        raise typer.Exit(code=0)