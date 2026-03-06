# B-TWIN Operations Runbook (P3)

## Incident triage order
1. Check dashboard: `GET /api/ops/dashboard`
2. Check indexer counters: `btwin indexer status`
3. Check gate violations from dashboard payload (`gateViolations`)

## Common incidents

### A. Failure queue growth (`failed`/`stale`)
1. `btwin indexer reconcile`
2. `btwin indexer refresh --limit 500`
3. Repair top offenders from `failureQueue`

### B. Gate rejection spike
1. Inspect recent `gateViolations`
2. Validate collab record checksum/vector presence
3. If persistent, run targeted repair for impacted `docId`

### C. Attached mode adapter errors
1. Validate OpenClaw config path (`btwin runtime show`)
2. Confirm runtime mode is `attached`
3. Fallback to standalone mode only for emergency continuity

## Recovery done criteria
- `indexerStatus.failed == 0`
- `indexerStatus.stale == 0` (or temporary known backlog)
- No new critical `gate_rejected` events in latest 30 min

## Escalation
- If recovery loop fails 2 times, freeze write operations and escalate to maintainer.
