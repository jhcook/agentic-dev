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

import typer
from agent.sync import sync as sync_ops

app = typer.Typer(
    help="Distributed synchronization (push, pull, status, scan).",
    no_args_is_help=True
)

@app.command()
def pull(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Pull artifacts from remote."""
    sync_ops.sync(verbose=verbose)

@app.command()
def push(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Push artifacts to remote."""
    sync_ops.push(verbose=verbose)

@app.command()
def status(detailed: bool = typer.Option(False, "--detailed", help="Show detailed list of artifacts")):
    """Check sync status."""
    sync_ops.status(detailed=detailed)

@app.command()
def delete(
    id: str = typer.Argument(..., help="Artifact ID to delete"),
    type: str = typer.Option(None, "--type", help="Specific artifact type (story, plan, runbook, adr)")
):
    """Delete artifact from local cache."""
    sync_ops.delete(id, type)

@app.command()
def scan(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Scan local file system and update cache."""
    sync_ops.scan(verbose=verbose)
