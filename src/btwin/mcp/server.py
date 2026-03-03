"""B-TWIN MCP Server — exposes core functionality as MCP tools.

Data-only architecture: MCP clients (Claude Code, Codex, Gemini CLI etc.)
provide the LLM brain. B-TWIN handles storage, search, and session management.
No API key required.
"""

import sys
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from btwin.config import BTwinConfig, load_config
from btwin.core.btwin import BTwin

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger(__name__)

mcp = FastMCP("btwin")

_twin: BTwin | None = None


def _get_twin() -> BTwin:
    global _twin
    if _twin is None:
        config_path = Path.home() / ".btwin" / "config.yaml"
        if config_path.exists():
            config = load_config(config_path)
        else:
            config = BTwinConfig()
        # Also check project-local config
        project_config = Path.cwd() / ".btwin" / "config.yaml"
        if project_config.exists() and project_config.resolve() != config_path.resolve():
            config = load_config(project_config)
        _twin = BTwin(config)
    return _twin


@mcp.tool()
def btwin_start_session(topic: str | None = None) -> str:
    """Start a new conversation session.

    Use this to explicitly begin tracking a conversation topic.
    If a session is already active, it will be replaced.

    Args:
        topic: Optional topic slug (e.g., "unreal-shader-study", "career-ta")
    """
    twin = _get_twin()
    result = twin.start_session(topic=topic)
    return f"Session started: {result.get('topic') or 'untitled'}"


@mcp.tool()
def btwin_end_session(summary: str, slug: str | None = None) -> str:
    """End the current session and save it as a searchable entry.

    The MCP client should provide a summary of the conversation.
    The summary is saved as a markdown entry and indexed for future search.

    Args:
        summary: A summary of the conversation (written by the MCP client LLM)
        slug: Optional filename slug (e.g., "unreal-shader-study"). Auto-generated from topic if omitted.
    """
    twin = _get_twin()
    result = twin.end_session(summary=summary, slug=slug)
    if result is None:
        return "No active session to end."
    return f"Session saved: {result['date']}/{result['slug']}\n\nSummary:\n{result['summary']}"


@mcp.tool()
def btwin_search(query: str, n_results: int = 5) -> str:
    """Search past entries by semantic similarity.

    Returns relevant past records that match the query.
    Use this to retrieve context from previous conversations.

    Args:
        query: The search query
        n_results: Maximum number of results to return (default: 5)
    """
    twin = _get_twin()
    results = twin.search(query, n_results=n_results)
    if not results:
        return "No matching records found."
    lines = []
    for r in results:
        lines.append(f"### {r['metadata'].get('slug', 'unknown')} ({r['metadata'].get('date', '')})")
        lines.append(r["content"])
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def btwin_record(content: str, topic: str | None = None) -> str:
    """Manually record a note or thought.

    Saves the content as a markdown entry and indexes it for future search.

    Args:
        content: The text content to record
        topic: Optional topic slug (e.g., "career-ta", "unreal-study")
    """
    twin = _get_twin()
    result = twin.record(content, topic=topic)
    return f"Recorded: {result['path']}"


@mcp.tool()
def btwin_session_status() -> str:
    """Check the current session status.

    Returns whether a session is active and its topic.
    """
    twin = _get_twin()
    status = twin.session_status()
    if not status["active"]:
        return "No active session."
    return (
        f"Active session: {status.get('topic') or 'untitled'}\n"
        f"Messages: {status['message_count']}\n"
        f"Started: {status['created_at']}"
    )


@mcp.resource("btwin://entries")
def list_entries() -> str:
    """List all recorded entries."""
    twin = _get_twin()
    entries = twin.storage.list_entries()
    if not entries:
        return "No entries yet."
    lines = []
    for e in entries:
        lines.append(f"- {e.date}/{e.slug}")
    return "\n".join(lines)


@mcp.resource("btwin://entries/{date}/{slug}")
def read_entry(date: str, slug: str) -> str:
    """Read a specific entry by date and slug."""
    twin = _get_twin()
    entry = twin.storage.read_entry(date, slug)
    if entry is None:
        return f"Entry not found: {date}/{slug}"
    return entry.content


@mcp.resource("btwin://summary")
def get_summary() -> str:
    """Get the cumulative summary of all records."""
    twin = _get_twin()
    summary_path = twin.config.data_dir / "summary.md"
    if summary_path.exists():
        return summary_path.read_text()
    return "No summary available yet."


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
