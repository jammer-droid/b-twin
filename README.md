# B-TWIN

A data-only MCP server that stores, searches, and manages personal records.
MCP clients (Claude Code, Codex CLI, Gemini CLI, etc.) provide the LLM brain — no API key required.

## Architecture

```
MCP Client (Claude Code, etc.)
    | MCP protocol (stdio)
B-TWIN MCP Server (FastMCP)
    |
B-TWIN Core Library
    +-- Storage (markdown files with YAML frontmatter)
    +-- VectorStore (ChromaDB, semantic search)
    +-- SessionManager (conversation lifecycle)
    |
Data Layer
    +-- ~/.btwin/entries/{date}/{slug}.md
    +-- ~/.btwin/index/ (ChromaDB)
    +-- ~/.btwin/summary.md (cumulative)
```

## Installation

```bash
git clone https://github.com/jammer-droid/b-twin.git
cd b-twin
./install.sh
```

`install.sh` handles everything:

1. Checks for [uv](https://docs.astral.sh/uv/) and installs it if missing
2. Installs Python dependencies (`uv sync`)
3. Creates `~/.btwin/` global data directory
4. Generates `~/.btwin/serve.sh` wrapper script

After installation, add the following to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "btwin": {
      "command": "~/.btwin/serve.sh",
      "args": []
    }
  }
}
```

> Replace `~` with your actual home directory path (e.g., `/Users/you/.btwin/serve.sh`).
> The exact snippet with the correct path is printed at the end of `install.sh`.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `btwin_start_session(topic?)` | Start tracking a conversation topic |
| `btwin_end_session(summary, slug?)` | Save session as a searchable entry |
| `btwin_search(query, n_results?)` | Semantic search over past entries |
| `btwin_record(content, topic?)` | Quick note without session lifecycle |
| `btwin_session_status()` | Check current session state |

## MCP Resources

| Resource | Purpose |
|----------|---------|
| `btwin://entries` | List all entries |
| `btwin://entries/{date}/{slug}` | Read a specific entry |
| `btwin://summary` | Cumulative summary |

## Usage

Once connected via MCP, your AI assistant can use B-TWIN tools naturally:

- **Record a thought:** "Save a note about today's architecture decision"
- **Search past entries:** "What did I write about career planning?"
- **Session tracking:** "Start tracking this conversation" / "Save this session"

## Data Path Resolution

B-TWIN resolves the data directory with the following precedence:

1. `BTWIN_DATA_DIR` environment variable
2. Per-project `.btwin/` directory (if it exists in CWD)
3. Global `~/.btwin/` (default)

## Entry Format

Entries are stored as markdown files with YAML frontmatter:

```markdown
---
created_at: '2026-03-02T12:30:00+00:00'
date: '2026-03-02'
slug: career-planning
topic: career
---

# Career Planning

Your content here...
```

## Tech Stack

- **Python** 3.11+
- **uv** — package manager
- **FastMCP** (`mcp[cli]`) — MCP server SDK
- **ChromaDB** — local vector DB for semantic search (no API key)
- **Typer + Rich** — CLI
- **Pydantic** — config validation
- **PyYAML** — frontmatter serialization

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest -v

# Start MCP server manually
uv run btwin serve
```

## License

MIT
