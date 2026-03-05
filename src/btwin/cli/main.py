"""B-TWIN CLI — command-line interface."""

import re
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown

from btwin.config import BTwinConfig, load_config
from btwin.core.sources import SourceRegistry

app = typer.Typer(
    name="btwin",
    help="B-TWIN: AI partner that remembers your thoughts.",
)
sources_app = typer.Typer(help="Manage B-TWIN data sources for dashboard workflows.")
promotion_app = typer.Typer(help="Manage promotion queue operations.")
indexer_app = typer.Typer(help="Manage core indexer workflows.")
app.add_typer(sources_app, name="sources")
app.add_typer(promotion_app, name="promotion")
app.add_typer(indexer_app, name="indexer")

console = Console(soft_wrap=True)

def _config_path() -> Path:
    return Path.home() / ".btwin" / "config.yaml"


def _get_config() -> BTwinConfig:
    config_path = _config_path()
    if config_path.exists():
        return load_config(config_path)
    return BTwinConfig()


def _get_registry() -> SourceRegistry:
    return SourceRegistry(Path.home() / ".btwin" / "sources.yaml")


def _is_valid_cron_schedule(value: str) -> bool:
    parts = value.strip().split()
    if len(parts) != 5:
        return False
    token_pattern = re.compile(r"^[0-9*/,\-]+$")
    return all(bool(token_pattern.match(part)) for part in parts)


def _atomic_write_yaml(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    tmp_path.replace(path)


@app.command()
def setup():
    """Interactive setup — configure API key and preferences."""
    config_path = _config_path()
    config_dir = config_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]B-TWIN Setup[/bold]\n")

    provider = typer.prompt("LLM provider", default="anthropic")
    model = typer.prompt("Model name", default="claude-haiku-4-5-20251001")
    api_key = typer.prompt("API key", hide_input=True)

    config_data = {
        "llm": {
            "provider": provider,
            "model": model,
            "api_key": api_key,
        },
        "session": {"timeout_minutes": 10},
        "promotion": {"enabled": True, "schedule": "0 9,21 * * *"},
        "data_dir": str(Path.home() / ".btwin"),
    }

    _atomic_write_yaml(config_path, config_data)

    console.print(f"\n[green]Config saved to {config_path}[/green]")


@app.command()
def serve():
    """Start the B-TWIN MCP server (stdio transport)."""
    import sys
    from rich.console import Console as _ErrConsole
    _ErrConsole(stderr=True).print("[bold]Starting B-TWIN MCP server...[/bold]")
    from btwin.mcp.server import main as mcp_main
    mcp_main()


@app.command("serve-api")
def serve_api(
    host: str = typer.Option("127.0.0.1", help="Host to bind HTTP API"),
    port: int = typer.Option(8787, help="Port for HTTP API"),
):
    """Start the B-TWIN HTTP API server for collab workflow."""
    import uvicorn
    from btwin.api.collab_api import create_default_collab_app

    console.print(f"[bold]Starting B-TWIN HTTP API on http://{host}:{port}[/bold]")
    app_instance = create_default_collab_app()
    uvicorn.run(app_instance, host=host, port=port)


@app.command()
def search(query: str, n: int = typer.Option(5, help="Number of results")):
    """Search past entries by semantic similarity."""
    from btwin.core.btwin import BTwin

    config = _get_config()
    twin = BTwin(config)
    results = twin.search(query, n_results=n)

    if not results:
        console.print("[yellow]No matching records found.[/yellow]")
        return

    for r in results:
        console.print(f"\n[bold cyan]{r['metadata'].get('date', '')}/{r['metadata'].get('slug', '')}[/bold cyan]")
        console.print(Markdown(r["content"][:500]))
        console.print("---")


@app.command()
def record(content: str, topic: str = typer.Option(None, help="Topic slug")):
    """Manually record a note."""
    from btwin.core.btwin import BTwin

    config = _get_config()
    twin = BTwin(config)
    result = twin.record(content, topic=topic)
    console.print(f"[green]Recorded: {result['path']}[/green]")


@app.command()
def chat():
    """Interactive chat with B-TWIN (REPL mode)."""
    from btwin.core.btwin import BTwin

    config = _get_config()
    twin = BTwin(config)

    console.print("[bold]B-TWIN Chat[/bold] — Type /quit to exit, /end to end session.\n")

    while True:
        try:
            user_input = console.input("[bold green]> [/bold green]")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.strip() == "/quit":
            result = twin.end_session()
            if result:
                console.print(f"\n[dim]Session saved: {result['date']}/{result['slug']}[/dim]")
            break

        if user_input.strip() == "/end":
            result = twin.end_session()
            if result:
                console.print(f"\n[dim]Session saved: {result['date']}/{result['slug']}[/dim]")
            else:
                console.print("[yellow]No active session.[/yellow]")
            continue

        if not user_input.strip():
            continue

        response = twin.chat(user_input)
        console.print(f"\n[bold blue]B-TWIN:[/bold blue] {response}\n")


@sources_app.command("list")
def sources_list(refresh: bool = typer.Option(False, "--refresh", help="Refresh entry counts before listing")):
    """List registered data sources."""
    registry = _get_registry()
    registry.ensure_global_default()
    if refresh:
        sources = registry.refresh_entry_counts()
    else:
        sources = registry.load()

    if not sources:
        console.print("[yellow]No data sources registered.[/yellow]")
        return

    for s in sources:
        status = "enabled" if s.enabled else "disabled"
        console.print(
            f"- [bold]{s.name}[/bold] ({status})\n"
            f"  path: {s.path}\n"
            f"  entries: {s.entry_count}\n"
            f"  last_scanned_at: {s.last_scanned_at or '-'}"
        )


@sources_app.command("add")
def sources_add(
    path: str = typer.Argument(..., help="Path to .btwin directory or project root containing .btwin"),
    name: str | None = typer.Option(None, help="Optional source name"),
    disabled: bool = typer.Option(False, "--disabled", help="Register source as disabled"),
):
    """Add a data source."""
    registry = _get_registry()
    p = Path(path).expanduser()

    # Allow passing either the .btwin dir or a project root containing .btwin
    candidate = p / ".btwin" if p.name != ".btwin" and (p / ".btwin").is_dir() else p

    if not candidate.exists() or not candidate.is_dir():
        raise typer.BadParameter(f"Source directory not found: {candidate}")

    src = registry.add_source(candidate, name=name, enabled=not disabled)
    state = "enabled" if src.enabled else "disabled"
    console.print(f"[green]Added source:[/green] {src.name} ({state}) -> {src.path}")


@sources_app.command("scan")
def sources_scan(
    root: str = typer.Argument(..., help="Root directory to scan for .btwin folders"),
    max_depth: int = typer.Option(4, help="Maximum scan depth"),
    register: bool = typer.Option(False, "--register", help="Register all discovered sources"),
):
    """Scan for candidate .btwin directories under a root path."""
    registry = _get_registry()
    candidates = registry.scan_for_btwin_dirs([Path(root)], max_depth=max_depth)

    if not candidates:
        console.print("[yellow]No .btwin directories found.[/yellow]")
        return

    console.print(f"Found {len(candidates)} candidate(s):")
    for c in candidates:
        console.print(f"- {c}")

    if register:
        for c in candidates:
            registry.add_source(c)
        console.print("[green]Registered all discovered sources.[/green]")


@sources_app.command("refresh")
def sources_refresh():
    """Refresh entry counts and scan timestamps for registered sources."""
    registry = _get_registry()
    registry.ensure_global_default()
    updated = registry.refresh_entry_counts()
    console.print(f"[green]Refreshed {len(updated)} source(s).[/green]")


@promotion_app.command("schedule")
def promotion_schedule(
    set_value: str | None = typer.Option(None, "--set", help="Set cron-style schedule expression"),
):
    """Show or update promotion batch schedule."""
    config_path = _config_path()

    if set_value is None:
        config = _get_config()
        console.print(f"Promotion schedule: [bold]{config.promotion.schedule}[/bold]")
        console.print(f"Enabled: {'yes' if config.promotion.enabled else 'no'}")
        return

    if not _is_valid_cron_schedule(set_value):
        raise typer.BadParameter("Invalid cron format. Expected 5 fields, e.g. '0 9,21 * * *'")

    raw: object = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text()) or {}

    data: dict[str, object] = raw if isinstance(raw, dict) else {}

    promotion_raw = data.get("promotion", {})
    promotion_cfg: dict[str, object]
    if isinstance(promotion_raw, dict):
        promotion_cfg = dict(promotion_raw)
    else:
        promotion_cfg = {}

    promotion_cfg["enabled"] = bool(promotion_cfg.get("enabled", True))
    promotion_cfg["schedule"] = set_value
    data["promotion"] = promotion_cfg

    _atomic_write_yaml(config_path, data)
    console.print(f"[green]Promotion schedule updated:[/green] {set_value}")


@promotion_app.command("run")
def promotion_run(limit: int | None = typer.Option(None, min=1, help="Max approved items to process")):
    """Run one promotion batch (approved -> queued -> promoted)."""
    from btwin.core.promotion_store import PromotionStore
    from btwin.core.promotion_worker import PromotionWorker
    from btwin.core.storage import Storage

    config = _get_config()
    storage = Storage(config.data_dir)
    store = PromotionStore(config.data_dir / "promotion_queue.yaml")
    worker = PromotionWorker(storage=storage, promotion_store=store)

    result = worker.run_once(limit=limit)
    console.print(
        "[green]Promotion batch done[/green] "
        f"processed={result['processed']} promoted={result['promoted']} "
        f"skipped={result['skipped']} errors={result['errors']}"
    )


@indexer_app.command("status")
def indexer_status():
    """Show indexer manifest status summary."""
    from btwin.core.indexer import CoreIndexer

    config = _get_config()
    idx = CoreIndexer(data_dir=config.data_dir)
    summary = idx.status_summary()
    console.print(
        "Indexer status "
        f"total={summary.get('total', 0)} "
        f"indexed={summary.get('indexed', 0)} "
        f"pending={summary.get('pending', 0)} "
        f"stale={summary.get('stale', 0)} "
        f"failed={summary.get('failed', 0)} "
        f"deleted={summary.get('deleted', 0)}"
    )


@indexer_app.command("refresh")
def indexer_refresh(limit: int | None = typer.Option(None, min=1, help="Max docs to process in this run")):
    """Refresh pending/stale/failed/deleted docs into vector index."""
    from btwin.core.indexer import CoreIndexer

    config = _get_config()
    idx = CoreIndexer(data_dir=config.data_dir)
    result = idx.refresh(limit=limit)
    console.print(
        "Indexer refresh "
        f"processed={result['processed']} indexed={result['indexed']} "
        f"deleted={result['deleted']} failed={result['failed']}"
    )


@indexer_app.command("reconcile")
def indexer_reconcile():
    """Reconcile file system docs with manifest and refresh index."""
    from btwin.core.indexer import CoreIndexer

    config = _get_config()
    idx = CoreIndexer(data_dir=config.data_dir)
    result = idx.reconcile()
    console.print(
        "Indexer reconcile "
        f"processed={result['processed']} indexed={result['indexed']} "
        f"deleted={result['deleted']} failed={result['failed']}"
    )


@indexer_app.command("repair")
def indexer_repair(doc_id: str = typer.Option(..., "--doc-id", help="Document id to repair")):
    """Repair a single manifest doc id by re-indexing source content."""
    from btwin.core.indexer import CoreIndexer

    config = _get_config()
    idx = CoreIndexer(data_dir=config.data_dir)
    result = idx.repair(doc_id)
    status = "ok" if result.get("ok") else "failed"
    console.print(f"Indexer repair {status} doc_id={doc_id} status={result.get('status')}")


if __name__ == "__main__":
    app()
