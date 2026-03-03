# B-TWIN Dashboard Product Spec (v1)

Date: 2026-03-03
Status: Draft (agreed decisions reflected)

## 1. Problem & Goal

### Problem
- MCP integration is powerful but can be inconvenient for users who want explicit record/search workflows.
- Current architecture resolves to one active data directory at a time, so multi-source visibility and management are limited.

### Goal
Build a **local-first dashboard** that lets users explicitly browse, record, search, and review memory data **without requiring MCP clients**.

## 2. Product Direction (Decided)

1. **Deployment model:** Local-only (`btwin ui`).
2. **UX strategy:**
   - Explicit, user-driven note management as the default path.
   - Session workflows remain available, but secondary.
3. **Knowledge graph strategy:**
   - **Explicit links first** (`related` field) for trustable graph edges.
   - Similarity search as an assistive layer (candidate suggestions), not auto-committed edges.

## 3. MVP Scope (v1)

## 3.1 Core Features
1. Entry list + search view
2. Entry detail view (frontmatter + markdown body)
3. Explicit note creation UI (quick capture + full editor)
4. Session history view
5. `summary.md` view/edit UI
6. Data source management (global/project `.btwin` sources)

## 3.2 Data Source Discovery & Management (Decided)
- Auto-register global default: `~/.btwin`
- Project sources discovered via **user-triggered scan** (not always-on crawling)
- Found paths are shown as candidates; user confirms before registration
- Registered source metadata:
  - `name`
  - `path`
  - `enabled`
  - `lastScannedAt`
  - `entryCount`
- Query/search aggregates only enabled sources

## 4. Information Architecture (IA)

- **Home**: quick capture, recent entries, recent sessions
- **Entries**: list/search/filter + detail panel
- **Sessions**: session history and summaries
- **Summary**: `summary.md` management
- **Sources**: data source registration/scan/enable toggles
- **Graph** (v1.1+): explicit-link graph and related exploration

## 5. Primary UX Flows

## 5.1 Quick Capture (default note path)
1. User writes note content in quick input
2. Save requested
3. System computes top-k similar entries
4. UI shows suggested related entries
5. User confirms selected links
6. Entry saved with approved `related` links

## 5.2 Search & Recall
1. User enters query
2. Results shown across enabled sources
3. Sort options: recency / relevance (semantic)
4. Filter options (v1 baseline): source, date range

## 5.3 Source Scan
1. User chooses root path(s) for scan
2. System discovers `.btwin` directories with depth/exclusion rules
3. Candidate list shown for approval
4. Approved candidates added to source registry

## 6. Data Model & Frontmatter (v1 Draft)

Current fields already in use:
- `topic`
- `created_at`
- `date`
- `slug`

Proposed expansion:
- `id`
- `title`
- `source` (`global` | `project`)
- `project`
- `tags`
- `importance`
- `emotion`
- `related` (list of entry ids)
- `session_id`

Principles:
- Keep backward compatibility
- New fields start optional
- No automatic write of similarity edges without user confirmation

## 7. Graph Strategy (v1.1+)

- Node identity: `id`
- Primary edge: `related`
- Grouping/filter metadata: `topic`, `tags`, `project`, `source`, `session_id`, `created_at`
- Similarity edges are optional overlays, user-adjustable by threshold, and not persisted by default

## 8. Non-Goals (for v1)

- Cloud sync / multi-user collaboration
- Background auto-crawl of entire filesystem
- Full Obsidian-parity graph interactions
- Automatic session-start recall enforcement

## 9. Open Questions / Deferred

1. **Automatic recall at new session start** (Deferred)
   - Option A: MCP prompts capability
   - Option B: system prompt instruction
   - Decision: gather usage feedback first, then lock implementation

2. **Advanced visualization scope**
   - Timeline/calendar and topic clustering are planned but can be staged after core MVP stability

## 10. Success Criteria (v1)

- User can store and retrieve notes without MCP setup
- User can manage multiple `.btwin` sources from one dashboard
- User can explicitly build trusted graph links during note creation
- Core flows are stable with local-only setup and no external API dependency
