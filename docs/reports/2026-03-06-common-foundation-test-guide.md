---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# Common foundation verification and handoff guide

This document captures the current MVP foundation shared by upcoming workflow orchestration and record/dashboard work.

It is intentionally about the **base layer** that now exists in the repo, not the full workflow/dashboard feature set that will sit on top of it later.

## 1) What the common foundation now provides

### Shared metadata contract
- `src/btwin/core/common_record_models.py`
- `CommonRecordMetadata` validates the minimum shared fields used by future workflow/dashboard-visible records:
  - `docVersion`
  - `status`
  - `createdAt`
  - `updatedAt`
  - `recordType`
- Datetimes must be timezone-aware and text fields must be non-empty.

### Deterministic shared-record storage
- `src/btwin/core/storage.py`
- `Storage.save_shared_record(...)` now persists shared docs under:
  - `entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md`
- This gives future workflow/dashboard code a stable on-disk location for common records.

### Indexer compatibility for shared workflow docs
- `Storage.list_indexable_documents()` now includes `entries/shared/...` documents.
- Shared docs expose stable `doc_id`, `path`, `checksum`, and `record_type` values.
- Workflow docs can now flow through the existing indexer/manifest pipeline as first-class indexable records.
- Supporting details: `docs/reports/2026-03-06-common-foundation-indexer-check.md`

### Shared API route scaffold
- `src/btwin/api/collab_api.py`
- Base health routes now exist for future feature expansion:
  - `GET /api/workflows/health`
  - `GET /api/entries/health`
  - `GET /api/sources/health`
- These give workflow/dashboard work a predictable API grouping before feature-specific endpoints are added.

### Shared UI shell
- `src/btwin/api/collab_api.py`
- `GET /ui` now renders a minimal shared shell with navigation to:
  - `/ui/workflows`
  - `/ui/entries`
  - `/ui/sources`
  - `/ui/summary`
  - `/ops`
- Placeholder routes exist for the new shared surfaces so later UI work can plug into a consistent frame instead of starting from scratch.

### Recovery/audit contract
- `docs/reports/2026-03-06-common-foundation-recovery-contract.md`
- `tests/test_core/test_common_foundation_recovery.py`
- The foundation now documents and tests the minimum persisted state needed to reconstruct a resume pointer from:
  - shared-record frontmatter
  - deterministic path / `doc_id`
  - indexable checksum
  - audit payload identifiers
- This establishes the recovery substrate without shipping a full workflow recovery engine yet.

## 2) What the foundation does **not** yet provide

This phase intentionally stops at reusable substrate. It does **not** yet ship:

- full workflow orchestration CRUD/endpoints for epics, tasks, or task-runs
- queueing, dispatch, retry policy, escalation, or scheduler logic
- complete workflow state machine UX
- complete record/dashboard UX built on the new shell
- advanced dashboard visualization (kanban, graph, timeline, etc.)
- source inventory management implementation behind the new foundation routes
- automatic recovery/replay of interrupted workflow side effects
- feature-specific storage helpers such as `save_workflow_epic(...)`, `save_workflow_task(...)`, or `save_workflow_task_run(...)`

In short: the **rails are present**, but the actual workflow/dashboard product features still need to be built on those rails.

## 3) Manual verification guide

### 3.1 Prep

```bash
cd b-twin
uv sync
```

### 3.2 Focused foundation regression checks

Run the focused tests that define the common-foundation surface:

```bash
uv run pytest -q \
  tests/test_core/test_common_foundation_storage.py \
  tests/test_api/test_common_foundation_api.py \
  tests/test_api/test_common_foundation_ui.py \
  tests/test_core/test_common_foundation_recovery.py
```

What these prove:
- shared records save to deterministic paths
- shared workflow docs are indexable with stable `record_type`
- foundation API route groups exist
- shared UI shell loads and all foundation links resolve
- persisted file state + audit identifiers are enough to reconstruct a resume pointer

### 3.3 Start the HTTP API locally

```bash
uv run btwin serve-api --host 127.0.0.1 --port 8787
```

Then verify the foundation routes manually:

```bash
curl http://127.0.0.1:8787/api/workflows/health
curl http://127.0.0.1:8787/api/entries/health
curl http://127.0.0.1:8787/api/sources/health
```

Expected response shape:

```json
{
  "ok": true,
  "scope": "workflows",
  "status": "available"
}
```

(`scope` changes per route.)

### 3.4 Check the shared UI shell in a browser

Open:
- `http://127.0.0.1:8787/ui`
- `http://127.0.0.1:8787/ui/workflows`
- `http://127.0.0.1:8787/ui/entries`
- `http://127.0.0.1:8787/ui/sources`
- `http://127.0.0.1:8787/ui/summary`
- `http://127.0.0.1:8787/ops`

What to confirm:
- `/ui` shows the shared shell and all expected nav links
- `/ui/workflows`, `/ui/sources`, and `/ui/summary` resolve with non-404 placeholder pages
- `/ui/entries` and `/ops` still resolve through the existing app surfaces
- the shell provides a clean common landing point for future workflow/dashboard pages

### 3.5 Optional storage-level spot check

If you want to inspect the deterministic path behavior directly, create a shared record in a small Python snippet or through future feature code and confirm it lands under:

```text
<data_dir>/entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md
```

For workflow records, the frontmatter should include at least:
- `docVersion`
- `status`
- `createdAt`
- `updatedAt`
- `recordType`

### 3.6 Full regression baseline

Run the full suite before handoff:

```bash
uv run pytest -q
```

Current baseline for this foundation handoff:
- `304 passed, 5 skipped`

## 4) What can now be built on top of this

### Workflow work can now build on:
- stable markdown/frontmatter storage for workflow artifacts
- predictable workflow `record_type` values for filtering and indexing
- a reserved API namespace at `/api/workflows/*`
- a reserved UI surface at `/ui/workflows`
- a documented persisted-state recovery contract for task-run resumption logic

Concretely, the next workflow layer can add:
- epic/task/task-run document helpers
- workflow CRUD endpoints
- transition enforcement and queue progression
- retry/escalation policies
- recovery/resume execution logic grounded in persisted state

### Dashboard work can now build on:
- shared document conventions usable across workflow-visible and dashboard-visible records
- reserved API namespaces at `/api/entries/*` and `/api/sources/*`
- a shared shell at `/ui` that prevents navigation/layout drift
- existing entries/ops screens that can be integrated into a broader dashboard experience

Concretely, the next dashboard layer can add:
- record browsing/search/filter screens behind the shared shell
- source inventory and refresh views
- summary/overview pages
- richer visualizations without rethinking base routing/layout conventions

## 5) Intended handoff summary

The common-foundation MVP should be treated as **infrastructure completion**, not feature completion.

Done now:
- metadata contract
- deterministic shared storage path
- indexer compatibility
- API route grouping scaffold
- shared UI shell
- persisted-state recovery/audit contract

Still to do later:
- actual workflow product behavior
- actual dashboard product behavior
- richer source/summary implementations
- orchestration/recovery policies above this substrate
