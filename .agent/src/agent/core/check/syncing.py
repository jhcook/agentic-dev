# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0 (the "License");
from rich.console import Console
from agent.core.logger import get_logger

logger = get_logger(__name__)

def sync_oracle_pattern(console: Console) -> None:
    """Implement NotebookLM / Notion Sync."""
    console.print("\n[bold blue]🔄 Verifying Notion Sync Status (Oracle Pattern)...[/bold blue]")
    try:
        from agent.sync.notion import NotionSync
        NotionSync()
        console.print("[green]✅ Notion sync ready (Oracle Pattern context active).[/green]")
    except Exception as e:
        logger.warning("Notion sync unreachable", extra={"error": str(e)})
        console.print(f"[yellow]⚠️  Notion sync unreachable: {e}. Oracle Pattern may have stale context.[/yellow]")
        
    notebooklm_ready = False
    console.print("\n[bold blue]🔄 Synchronizing NotebookLM Context (Oracle Pattern)...[/bold blue]")
    try:
        import asyncio
        from agent.sync.notebooklm import ensure_notebooklm_sync
        from rich.status import Status
        
        with Status("Synchronizing NotebookLM Context...", console=console) as _sync_status:
            def _update_notebooklm_status(msg: str):
                _sync_status.update(f"Synchronizing NotebookLM Context... [dim]{msg}[/dim]")
            
            sync_status = asyncio.run(ensure_notebooklm_sync(progress_callback=_update_notebooklm_status))
            
        if sync_status == "SUCCESS":
            console.print("[green]✅ NotebookLM sync ready.[/green]")
            notebooklm_ready = True
        elif sync_status == "NOT_CONFIGURED":
            console.print("[yellow]ℹ️  NotebookLM sync not configured.[/yellow]")
        else:
            console.print("[yellow]⚠️  NotebookLM sync unavailable or degraded.[/yellow]")
    except Exception as e:
        logger.warning("NotebookLM sync unreachable", extra={"error": str(e)})
        console.print(f"[yellow]⚠️  NotebookLM sync unreachable: {e}.[/yellow]")

    if not notebooklm_ready:
        console.print("\n[bold blue]🔄 Rebuilding Local Vector DB (Oracle Pattern Fallback)...[/bold blue]")
        try:
            from agent.db.journey_index import JourneyIndex
            idx = JourneyIndex()
            idx.build()
            console.print("[green]✅ Local Vector DB ready.[/green]")
        except Exception as e:
            logger.error("Local Vector DB build failed", extra={"error": str(e)})
            console.print(f"[yellow]⚠️  Local Vector DB build failed: {e}.[/yellow]")
