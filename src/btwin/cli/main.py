"""B-TWIN CLI — command-line interface."""

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
app.add_typer(sources_app, name="sources")

console = Console(soft_wrap=True)

CONFIG_PATH = Path.home() / ".btwin" / "config.yaml"


def _get_config() -> BTwinConfig:
    if CONFIG_PATH.exists():
        return load_config(CONFIG_PATH)
    return BTwinConfig()


def _get_registry() -> SourceRegistry:
    return SourceRegistry(Path.home() / ".btwin" / "sources.yaml")


@app.command()
def setup():
    """Interactive setup — configure API key and preferences."""
    config_dir = CONFIG_PATH.parent
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
        "data_dir": str(Path.home() / ".btwin"),
    }

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    console.print(f"\n[green]Config saved to {CONFIG_PATH}[/green]")


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


if __name__ == "__main__":
    app()
