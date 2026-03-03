"""B-TWIN CLI — command-line interface."""

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown

from btwin.config import BTwinConfig, load_config
from btwin.core.btwin import BTwin

app = typer.Typer(
    name="btwin",
    help="B-TWIN: AI partner that remembers your thoughts.",
)
console = Console()

CONFIG_PATH = Path.home() / ".btwin" / "config.yaml"


def _get_config() -> BTwinConfig:
    if CONFIG_PATH.exists():
        return load_config(CONFIG_PATH)
    return BTwinConfig()


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


@app.command()
def search(query: str, n: int = typer.Option(5, help="Number of results")):
    """Search past entries by semantic similarity."""
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
    config = _get_config()
    twin = BTwin(config)
    result = twin.record(content, topic=topic)
    console.print(f"[green]Recorded: {result['path']}[/green]")


@app.command()
def chat():
    """Interactive chat with B-TWIN (REPL mode)."""
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


if __name__ == "__main__":
    app()
