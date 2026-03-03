# B-TWIN Architecture Decisions

## Overview

B-TWIN is a data-only MCP server that stores, searches, and manages personal records.
MCP clients (Claude Code, Codex CLI, Gemini CLI, etc.) provide the LLM brain.
No API key required for the MCP server — it handles only storage and retrieval.

## Current Architecture (v0.1)

```
MCP Client (Claude Code, etc.)
    ↓ MCP protocol (stdio)
B-TWIN MCP Server (FastMCP)
    ↓
B-TWIN Core Library
    ├── Storage (markdown files)
    ├── VectorStore (ChromaDB, semantic search)
    ├── SessionManager (conversation lifecycle)
    └── LLMClient (optional, CLI-only)
    ↓
Data Layer
    ├── ~/.btwin/entries/{date}/{slug}.md
    ├── ~/.btwin/index/ (ChromaDB)
    └── ~/.btwin/summary.md (cumulative)
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `btwin_start_session(topic?)` | Start tracking a conversation topic |
| `btwin_end_session(summary, slug?)` | Save session as searchable entry |
| `btwin_search(query, n_results?)` | Semantic search over past entries |
| `btwin_record(content, topic?)` | Quick note without session lifecycle |
| `btwin_session_status()` | Check current session state |

## MCP Resources

| Resource | Purpose |
|----------|---------|
| `btwin://entries` | List all entries |
| `btwin://entries/{date}/{slug}` | Read specific entry |
| `btwin://summary` | Cumulative summary |

## Installation

```bash
git clone <repo>
cd btwin-service
./install.sh
```

`install.sh` does:
1. Check/install `uv` (Python package manager)
2. `uv sync` (install dependencies + create venv)
3. Create `~/.btwin/` (global data directory)
4. Generate `~/.btwin/serve.sh` (MCP server wrapper with baked-in service path)
5. Output `.mcp.json` snippet for user to copy into their project

User adds to their project's `.mcp.json`:
```json
{
  "mcpServers": {
    "btwin": {
      "command": "<HOME>/.btwin/serve.sh",
      "args": []
    }
  }
}
```

## Data Path Resolution

Precedence (highest to lowest):
1. `BTWIN_DATA_DIR` environment variable
2. Per-project `.btwin/` directory (if exists in CWD)
3. Global `~/.btwin/` (default)

## Key Decisions

### 2026-03-02: Data-Only MCP Architecture

**Decision:** Remove LLM dependency from MCP server. MCP clients ARE the LLM.

**Rationale:** Users already have Claude Code / Codex / Gemini CLI — requiring a separate API key for B-TWIN creates redundancy and cost. The MCP server should only handle data operations.

**Impact:** `btwin_chat` tool removed. `btwin_end_session` now requires `summary` parameter from the MCP client.

### 2026-03-03: Remove Skills Layer + `btwin init`

**Decision:** Remove SKILL.md templates and `btwin init` CLI command.

**Rationale:**
- MCP tools are already discoverable by MCP clients without explicit skills
- Skills require copying files to every project that uses B-TWIN — unnecessary friction
- The explicit invocation UX (`/btwin-record`) is better served by a web dashboard

**Cleanup:**
- Remove `src/btwin/skills/` directory
- Remove `btwin init` command from `src/btwin/cli/main.py`
- Remove `tests/test_cli/test_init.py`
- Remove btwin-* skill files from consumer projects

### 2026-03-03: install.sh + serve.sh Wrapper

**Decision:** Use a shell script for installation instead of `btwin init`.

**Rationale:**
- `install.sh` runs once from the cloned repo — handles everything
- `serve.sh` wrapper eliminates hardcoded paths in `.mcp.json`
- Users copy a fixed JSON snippet from README — no path editing needed

### 2026-03-03: Web Dashboard (Future)

**Decision:** Build a web-based dashboard instead of CLI skills for explicit data management.

**Rationale:**
- Visualization is essential for reviewing accumulated records
- Dashboard can manage both global (`~/.btwin/`) and per-project (`.btwin/`) data in one place
- Provides explicit UI actions (record, search, browse) without requiring MCP client
- Better UX than slash commands for data review and management

**Planned features:**
- Browse and search entries across all data sources (global + per-project)
- Timeline/calendar view of entries
- Topic clustering and visualization
- `summary.md` management
- Session history
- Explicit record/search UI (usable without any MCP client)

### 2026-03-03: UX Direction for Open Source Adoption

**Decision:** Keep MCP integration as the power-user path, and complement it with explicit non-MCP UX.

**Rationale:**
- MCP-only onboarding can feel heavy for first-time/open-source users
- A direct UI path reduces setup friction and improves first-run success
- This keeps protocol flexibility (MCP) while improving accessibility for non-MCP users

**Direction:**
- Track A: MCP integration for coding-agent workflows
- Track B: explicit dashboard UX for browsing, recording, and searching entries

### 2026-03-03: Automatic Recall at New Session Start (Deferred)

**Status:** Deferred for now ("use more and decide later").

**Problem:** At new session start, Claude does not always automatically reference existing B-TWIN records.

**Options under consideration:**
- Use MCP `prompts` capability to guide initial recall behavior
- Add explicit B-TWIN search instruction in system prompt

**Decision for now:** Do not lock implementation yet; gather more usage feedback first.

### 2026-03-03: Frontmatter Metadata Expansion (Planned)

**Current state:** Entries currently store `topic`, `created_at`, `date`, `slug`.

**Decision:** Expand metadata schema to better support dashboard visualization and navigation.

**Candidate fields:**
- `tags`
- `category`
- `emotion` / `importance` labels
- related-entry links

**Notes:**
- Keep backward compatibility with existing entries
- Avoid overfitting early; start with optional fields

## Tech Stack

- **Runtime:** Python 3.11+
- **Package manager:** uv
- **MCP SDK:** FastMCP (`mcp[cli]`)
- **Vector DB:** ChromaDB (local, no API key)
- **LLM (optional):** LiteLLM (CLI standalone mode only)
- **CLI:** Typer + Rich
- **Config:** Pydantic + PyYAML
