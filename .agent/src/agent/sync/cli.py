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
from agent.core.auth.decorators import with_creds
from agent.core.notion.client import NotionClient
from agent.sync.janitor import NotionJanitor
import logging

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Distributed synchronization (push, pull, status, scan).",
    no_args_is_help=True
)

@app.command()
@with_creds(check_llm=False)
def pull(
    artifact_id: str = typer.Argument(None, help="Specific artifact ID to pull (e.g. INFRA-001)"),
    type: str = typer.Option(None, "--type", help="Specific artifact type (story, plan, runbook, adr)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    backend: str = typer.Option(None, "--backend", help="Specific backend to use (e.g. notion)"),
    force: bool = typer.Option(False, "--force", help="Force overwrite without prompting")
):
    """Pull artifacts from remote."""
    sync_ops.pull(verbose=verbose, backend=backend, force=force, artifact_id=artifact_id, artifact_type=type)

@app.command()
@with_creds(check_llm=False)
def push(
    artifact_id: str = typer.Argument(None, help="Specific artifact ID to push (e.g. INFRA-001)"),
    type: str = typer.Option(None, "--type", help="Specific artifact type (story, plan, runbook, adr)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    backend: str = typer.Option(None, "--backend", help="Specific backend to use (e.g. notion)"),
    force: bool = typer.Option(False, "--force", help="Force overwrite without prompting")
):
    """Push artifacts to remote."""
    sync_ops.push(verbose=verbose, backend=backend, force=force, artifact_id=artifact_id, artifact_type=type)

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

@app.command()
def janitor(
    notion_api_key: str = typer.Option(None, envvar="NOTION_TOKEN", help="Notion API Key"),
    database_id: str = typer.Option(None, envvar="NOTION_DB_ID", help="Notion Database ID (Stories)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without making changes"),
    backend: str = typer.Option(None, "--backend", help="Specific backend to use (e.g. notion)")
):
    """Run the Janitor to maintain relational integrity."""
    sync_ops.janitor(
        notion_api_key=notion_api_key, 
        database_id=database_id, 
        dry_run=dry_run, 
        backend=backend
    )

@app.command()
def init(backend: str = typer.Option(None, "--backend", help="Specific backend to initialize (e.g. notion)")):
    """Initialize/Bootstrap sync backends (create databases, etc)."""
    sync_ops.init(backend=backend)
