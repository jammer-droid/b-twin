---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# Indexer Operations (VS6)

> 용어 기준: `docs/glossary.md`

B-TWIN VS6 introduces a core indexer that keeps markdown source documents and Chroma vector index consistent.

## Status Model

Manifest status values:

- `pending`: new document waiting to be indexed
- `indexed`: vector index is in sync with source
- `stale`: source changed and needs re-indexing
- `failed`: indexing failed (retry/repair needed)
- `deleted`: source disappeared; vector cleanup needed

Manifest file path:

- `~/.btwin/index_manifest.yaml`

---

## CLI Commands

### 1) Status

```bash
btwin indexer status
```

Example output:

```text
Indexer status total=12 indexed=10 pending=1 stale=0 failed=1 deleted=0
```

### 2) Refresh (process queued statuses)

```bash
btwin indexer refresh --limit 100
```

- Processes `pending/stale/failed/deleted`
- Writes successful docs to vector index
- Removes vectors for `deleted`

### 3) Reconcile (filesystem ↔ manifest sync)

```bash
btwin indexer reconcile
```

- Scans indexable documents from storage
- Marks missing docs as `deleted`
- Triggers refresh run

### 4) Repair (single document)

```bash
btwin indexer repair --doc-id entries/convo/2026-03-05/convo-123.md
```

- Re-indexes one target document deterministically
- Useful when a specific doc is stuck in `failed`

---

## HTTP Admin API

All indexer endpoints are admin-scoped.

Common headers:

- `X-Admin-Token: <BTWIN_ADMIN_TOKEN>`
- `X-Actor-Agent: main` (must match body `actorAgent` if both are used)

### GET `/api/indexer/status`

Returns manifest summary.

### GET `/api/ops/dashboard`

Unified ops view containing:
- `indexerStatus`
- `failureQueue`
- `repairHistory`
- `gateViolations`
- `runtime.mode`
- `runtime.recallAdapter`
- `runtime.degraded`
- `runtime.degradedReason`

### GET `/ops`

Simple browser UI for the dashboard.
- If admin token is configured, enter token in the UI (`X-Admin-Token`) and click **Load**.

### POST `/api/indexer/refresh`

Body:

```json
{
  "actorAgent": "main",
  "limit": 100
}
```

### POST `/api/indexer/reconcile`

Body:

```json
{
  "actorAgent": "main"
}
```

### POST `/api/indexer/repair`

Body:

```json
{
  "actorAgent": "main",
  "docId": "entries/convo/2026-03-05/convo-123.md"
}
```

---

## Troubleshooting

### `failed` keeps increasing

1. Check document readability and path validity
2. Run targeted repair:

```bash
btwin indexer repair --doc-id <doc-id>
```

3. If many docs are affected, run:

```bash
btwin indexer refresh --limit 500
```

### docs marked `deleted` unexpectedly

- Source file may have moved/been removed.
- Restore source file, then run:

```bash
btwin indexer reconcile
```

### stale documents not catching up

- Run `btwin indexer refresh --limit N`
- If still stale, run `btwin indexer repair --doc-id ...` for targeted recovery

---

## Operational Recommendation

- Daily/periodic: `btwin indexer status`
- End-of-batch/session: `./scripts/end_of_batch_sync.sh` (default limit=200)
- On deployment/migration: `./scripts/end_of_batch_sync.sh 500`
- Incident recovery: `btwin indexer repair --doc-id ...` then `status`
