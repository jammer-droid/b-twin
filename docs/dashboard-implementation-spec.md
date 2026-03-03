# B-TWIN Dashboard Implementation Spec

Date: 2026-03-03
Status: Working spec for implementation
Related: `docs/dashboard-product-spec.md`, `docs/architecture-decisions.md`

## 1) Objective

Implement a local-only B-TWIN dashboard that enables explicit memory workflows without MCP dependency.

Primary outcomes:
- Users can register/manage multiple `.btwin` data sources.
- Users can browse/search entries across enabled sources.
- Users can create notes with explicit `related` links assisted by similarity suggestions.

## 2) Scope

### In Scope (v1)
1. Data source management (list/add/scan/enable/disable/refresh)
2. Entry list + detail (frontmatter/body)
3. Explicit note creation UI (quick + full form)
4. Session history view
5. `summary.md` read/edit
6. Save-time similarity suggestion flow (candidate only, user-confirmed)

### Out of Scope (v1)
- Cloud sync / multi-user
- Fully interactive Obsidian-grade graph
- Automatic forced recall on every new session
- Background filesystem-wide crawling

## 3) Architecture

## 3.1 Runtime Model
- Local process only
- Dashboard backend reads/writes local filesystem sources
- ChromaDB used for semantic search/similarity

## 3.2 Components
- **Core** (existing + expanded)
  - `core/sources.py` (source registry and scanning)
  - `core/storage.py` (entry persistence + frontmatter parsing)
  - `core/vector.py` (semantic search)
- **Service Layer** (new)
  - Source service (enable/disable/list/scan/register/refresh)
  - Entry query service (aggregate across enabled sources)
  - Similarity suggestion service
- **Dashboard API** (new)
  - Local HTTP endpoints for UI
- **Frontend** (new)
  - Pages: Home, Entries, Sessions, Summary, Sources

## 4) Data Contracts

## 4.1 Entry Frontmatter (v1 draft)
Required persisted fields:
- `date`, `slug`

Optional supported fields:
- `id`, `title`, `topic`, `tags`, `project`, `source`, `importance`, `emotion`, `related`, `session_id`, `created_at`

Rules:
- Preserve structured metadata types (lists/objects where applicable)
- `related` must contain entry ids/slugs only
- Similarity suggestions are never auto-committed without user confirmation

## 4.2 Source Registry Schema (`~/.btwin/sources.yaml`)
```yaml
sources:
  - name: global
    path: /Users/you/.btwin
    enabled: true
    last_scanned_at: 2026-03-03T12:00:00+00:00
    entry_count: 42
```

## 5) API Spec (local)

## 5.1 Sources
- `GET /api/sources`
  - returns registered sources
- `POST /api/sources`
  - body: `{ path, name?, enabled? }`
- `POST /api/sources/scan`
  - body: `{ roots: string[], maxDepth?: number }`
  - returns candidates (not auto-registered)
- `POST /api/sources/register-candidates`
  - body: `{ paths: string[] }`
- `PATCH /api/sources/{id}`
  - body: `{ enabled?: boolean, name?: string }`
- `POST /api/sources/refresh`
  - recomputes `entry_count`, updates `last_scanned_at`

## 5.2 Entries
- `GET /api/entries`
  - query: `q, source, from, to, sort(recency|relevance), page, size`
- `GET /api/entries/{entryId}`
- `POST /api/entries`
  - body includes content + metadata
  - optional `relatedCandidatesAccepted: string[]`

## 5.3 Similarity
- `POST /api/entries/similar`
  - body: `{ content, topic?, topK? }`
  - returns candidate related entries

## 5.4 Sessions & Summary
- `GET /api/sessions`
- `GET /api/summary`
- `PUT /api/summary`

## 6) UX Behavior Spec

## 6.1 Source Scan
- User-triggered only
- Must respect depth and exclusion rules
- Found candidates shown for manual approval

## 6.2 Quick Capture
1. User writes note
2. System requests similarity candidates
3. User checks desired related links
4. Save persists note + approved `related`

## 6.3 Search Defaults
- Default sort: recency
- Optional semantic relevance mode
- Filter by source/date

## 7) Implementation Plan (Engineering)

### Phase A — Backend foundation
- [ ] Add dashboard API server scaffold
- [ ] Add source endpoints using `SourceRegistry`
- [ ] Add aggregated entry query over enabled sources
- [ ] Add similarity endpoint

### Phase B — Frontend MVP
- [ ] Sources page (list/add/scan/register/enable)
- [ ] Entries page (list/detail/search)
- [ ] Quick capture form with related candidate selection
- [ ] Summary page (view/edit)
- [ ] Sessions page (basic list)

### Phase C — Hardening
- [ ] Error handling and empty-state UX
- [ ] Source path validation and duplicate prevention
- [ ] Regression tests (API + integration)

## 8) Testing Strategy

- Unit
  - source registry behavior
  - entry metadata preservation
  - candidate suggestion filtering
- API tests
  - source lifecycle
  - entry create/list/detail
- Integration
  - multi-source aggregation with enabled toggle
  - quick-capture -> suggestion -> save -> readback

## 9) Definition of Done (v1)

- Users can manage multiple local `.btwin` sources from dashboard
- Users can search and open entries across enabled sources
- Users can create notes and explicitly confirm related links
- Summary/session screens are functional
- Core + API tests pass in CI/local

## 10) Risks & Mitigations

- **Risk:** source explosion/performance on large trees
  - Mitigation: scan only on user action, bounded depth, exclusion set
- **Risk:** noisy similarity candidates
  - Mitigation: top-k cap + user confirmation only
- **Risk:** metadata schema drift
  - Mitigation: optional fields + backward compatibility parsing
