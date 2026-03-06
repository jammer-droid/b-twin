"""B-TWIN MCP Proxy -- lightweight MCP server that forwards to HTTP API.

Instead of importing heavy dependencies (chromadb, indexer, storage),
this proxy forwards MCP tool calls as HTTP requests to a running
B-TWIN API server, automatically injecting the projectId parameter.

Architecture:
    LLM Client -> MCP Proxy (project="myproj", backend="http://localhost:8787")
                     |
               HTTP POST /api/entries/record  {"content": "...", "projectId": "myproj"}
                     |
               B-TWIN HTTP API (serve-api)
"""

from __future__ import annotations

import sys
import logging

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger(__name__)

# Module-level state, set by main() before mcp.run().
_project: str = ""
_backend: str = "http://localhost:8787"
_client: httpx.Client | None = None

mcp = FastMCP("btwin")


def _http() -> httpx.Client:
    """Lazy-initialise and return the shared httpx client."""
    global _client
    if _client is None:
        _client = httpx.Client(base_url=_backend, timeout=30.0)
    return _client


def _post(path: str, data: dict) -> dict:
    """POST JSON to the backend API and return parsed response."""
    resp = _http().post(path, json=data)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, params: dict | None = None) -> dict:
    """GET from the backend API and return parsed response."""
    resp = _http().get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def _inject_project(data: dict) -> dict:
    """Return a copy of *data* with projectId injected (if configured)."""
    if _project:
        data["projectId"] = _project
    return data


# ---------------------------------------------------------------------------
# MCP Tools -- same names & signatures as server.py, forwarded via HTTP
# ---------------------------------------------------------------------------


@mcp.tool()
def btwin_record(content: str, topic: str | None = None) -> str:
    """Manually record a note or thought.

    Saves the content as a markdown entry and indexes it for future search.

    Args:
        content: The text content to record
        topic: Optional topic slug (e.g., "career-ta", "unreal-study")
    """
    data: dict = {"content": content}
    if topic:
        data["topic"] = topic
    _inject_project(data)
    result = _post("/api/entries/record", data)
    return f"Recorded: {result.get('path', 'ok')}"


@mcp.tool()
def btwin_search(
    query: str,
    n_results: int = 5,
    record_type: str | None = None,
    scope: str = "project",
) -> str:
    """Search past entries by semantic similarity.

    Returns relevant past records that match the query.

    Args:
        query: The search query
        n_results: Maximum number of results to return (default: 5)
        record_type: Optional metadata filter (e.g. convo, collab, entry)
        scope: "project" (default) searches current project only, "all" searches everything
    """
    data: dict = {"query": query, "nResults": n_results, "scope": scope}

    if scope != "all":
        # Only inject projectId for project-scoped searches
        _inject_project(data)

    result = _post("/api/entries/search", data)

    if not result:
        return "No matching records found."
    if isinstance(result, list):
        lines: list[str] = []
        for r in result:
            meta = r.get("metadata", {})
            lines.append(f"### {meta.get('slug', 'unknown')} ({meta.get('date', '')})")
            lines.append(r.get("content", ""))
            lines.append("")
        return "\n".join(lines) if lines else "No matching records found."
    return str(result)


@mcp.tool()
def btwin_convo_record(content: str, requested_by_user: bool = False) -> str:
    """Record user conversation memory.

    Args:
        content: Conversation memory content to store
        requested_by_user: Whether this was an explicit user remember request
    """
    data: dict = {"content": content, "requestedByUser": requested_by_user}
    _inject_project(data)
    result = _post("/api/entries/convo-record", data)
    return f"Convo recorded: {result.get('path', 'ok')}"


@mcp.tool()
def btwin_import_entry(
    content: str,
    date: str,
    slug: str,
    tags: str | None = None,
    source_path: str | None = None,
) -> str:
    """Import a single entry with explicit date, slug, and tags.

    Args:
        content: The markdown content of the entry
        date: Date in YYYY-MM-DD format (e.g., "2026-02-24")
        slug: Filename slug (e.g., "ea-interview-review")
        tags: Comma-separated tags (e.g., "jobs,ea-korea,interview")
        source_path: Original file path for dedup tracking
    """
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    data: dict = {"content": content, "date": date, "slug": slug}
    if tag_list:
        data["tags"] = tag_list
    if source_path:
        data["sourcePath"] = source_path
    _inject_project(data)
    result = _post("/api/entries/import", data)
    return f"Imported: {result.get('date', date)}/{result.get('slug', slug)} -> {result.get('path', 'ok')}"


@mcp.tool()
def btwin_start_session(topic: str | None = None) -> str:
    """Start a new conversation session.

    Args:
        topic: Optional topic slug (e.g., "unreal-shader-study", "career-ta")
    """
    data: dict = {}
    if topic:
        data["topic"] = topic
    # NOTE: SessionStartRequest has extra="forbid" and no projectId field,
    # so we must NOT inject projectId here.
    result = _post("/api/sessions/start", data)
    return f"Session started: {result.get('topic') or 'untitled'}"


@mcp.tool()
def btwin_end_session(summary: str, slug: str | None = None) -> str:
    """End the current session and save it as a searchable entry.

    Args:
        summary: A summary of the conversation
        slug: Optional filename slug
    """
    data: dict = {"summary": summary}
    if slug:
        data["slug"] = slug
    _inject_project(data)
    result = _post("/api/sessions/end", data)
    if result is None:
        return "No active session to end."
    return f"Session saved: {result.get('date', '?')}/{result.get('slug', '?')}"


@mcp.tool()
def btwin_session_status() -> str:
    """Check the current session status."""
    result = _get("/api/sessions/status")
    if not result.get("active"):
        return "No active session."
    return (
        f"Active session: {result.get('topic') or 'untitled'}\n"
        f"Messages: {result.get('message_count', 0)}\n"
        f"Started: {result.get('created_at', '?')}"
    )


def main() -> None:
    """CLI entry-point: parse --project/--backend, then run MCP over stdio."""
    import argparse

    parser = argparse.ArgumentParser(description="B-TWIN MCP Proxy")
    parser.add_argument("--project", required=True, help="Project name to bind")
    parser.add_argument(
        "--backend",
        default="http://localhost:8787",
        help="Backend API URL (default: http://localhost:8787)",
    )
    args = parser.parse_args()

    global _project, _backend
    _project = args.project
    _backend = args.backend

    log.info("B-TWIN MCP Proxy: project=%s backend=%s", _project, _backend)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
