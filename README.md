doc_version: 1

# B-TWIN

A data-only MCP server that stores, searches, and manages personal records.
MCP clients (Claude Code, Codex CLI, Gemini CLI, etc.) provide the LLM brain — no API key required.

## Architecture

```
Bot/Claude → MCP Proxy (project=X) → B-TWIN HTTP API (localhost:8787)
```

Each MCP client connects through a lightweight proxy that tags requests with a project identifier. The HTTP API server manages storage, indexing, and search.

```
~/.btwin/entries/
  _global/                    ← default project (no project specified)
    2026-03-06/slug.md
    convo/2026-03-06/slug.md
    collab/2026-03-06/slug.md
  my-project/                 ← project-specific entries
    2026-03-06/slug.md
    convo/2026-03-06/slug.md
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
4. Generates `~/.btwin/serve.sh` and `~/.btwin/proxy.sh` wrapper scripts

## Project Setup

**Claude Code / Codex CLI:**

```bash
cd my-project
./install.sh              # One-time: install B-TWIN
btwin serve-api            # Start the API server (keep running)
btwin init                 # Auto-detect project name from git, create .mcp.json
# or: btwin init my-project
```

`btwin init` generates `.mcp.json` that routes MCP traffic through the proxy with the correct project binding.

**OpenClaw bots:**

```yaml
mcp_servers:
  btwin:
    command: ~/.btwin/proxy.sh
    args: [--project, main]
```

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

## Migration

For existing users upgrading to project-partitioned storage:

```bash
python scripts/migrate_to_project_layout.py
btwin indexer reconcile
btwin indexer refresh
```

This moves existing entries under `_global/` and rebuilds the index.

## Indexer Operations (VS6)

Core indexer CLI commands:

```bash
btwin indexer status
btwin indexer refresh --limit 100
btwin indexer reconcile
btwin indexer repair --doc-id <doc-id>
```

Default end-of-batch sync helper (`refresh + reconcile` pipeline):

```bash
./scripts/end_of_batch_sync.sh        # default limit=200
./scripts/end_of_batch_sync.sh 500    # custom refresh limit
```

HTTP admin endpoints:

- `GET /api/indexer/status`
- `POST /api/indexer/refresh`
- `POST /api/indexer/reconcile`
- `POST /api/indexer/repair`

> These endpoints require admin token scope (`X-Admin-Token`) and main admin actor (`actorAgent: main`).

Detailed runbook: `docs/indexer-operations.md`

## Common Foundation MVP (workflow + dashboard base)

This repo now includes the shared foundation that future workflow orchestration and dashboard work can build on:

- deterministic shared-record storage under `entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md`
- indexer compatibility for shared workflow documents
- foundation API route groups:
  - `GET /api/workflows/health`
  - `GET /api/entries/health`
  - `GET /api/sources/health`
- shared UI shell at `GET /ui` with navigation to workflows / entries / sources / summary / ops
- documented persisted-state recovery contract for future workflow resume logic

To run the HTTP API locally:

```bash
uv run btwin serve-api
```

Verification / handoff guide:
- `docs/reports/2026-03-06-common-foundation-test-guide.md`

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
uv run --python 3.13 pytest -q

# Verify managed docs include doc_version
python scripts/doc_version_check.py

# Start MCP server manually
uv run btwin serve
```

## License

MIT
