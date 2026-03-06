# Common foundation recovery contract

## Scope

This contract defines the **minimum persisted-state and audit guarantees** that workflow/dashboard features can rely on during restart and recovery.

It is intentionally small:
- no hidden in-memory cursor is required to resume work
- recovery is derived from persisted markdown/frontmatter plus audit rows
- future workflow-specific dispatch logic can build on this without changing the storage/audit base

## Persisted state contract

Shared foundation records saved under `entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md` must retain enough information to compute a resume pointer from disk alone.

Minimum fields used by the contract:
- `recordId`
- `docVersion`
- `status`
- `updatedAt`
- `recordType`
- deterministic document path (`doc_id` / relative path)
- current checksum from indexable document enumeration

### Recovery assumption

A recovery loop can reconstruct the current resume pointer by reading:
1. the canonical shared record file frontmatter
2. the deterministic relative path / `doc_id`
3. the checksum exposed by `Storage.list_indexable_documents()`

That is enough to answer:
- which record should resume
- which persisted version is current
- which status was last committed
- which document path/checksum should be used for reconciliation

## Audit contract

For recovery-relevant audit events, the persisted row must keep identifiers exactly as written so reconstruction logic can correlate state transitions.

Required top-level audit row fields already provided by `AuditLogger`:
- `timestamp`
- `eventType`
- `traceId`
- `payload`

Recovery-oriented audit payloads should include the identifiers needed by the caller's workflow layer, typically:
- `recordId`
- `taskRunId` (or equivalent run identifier)
- `docId`
- `docVersion`
- current/recovered `status`
- optional recovery reason/context

## What this phase guarantees today

- Shared records are stored at a stable, deterministic path.
- Latest persisted frontmatter is sufficient to compute a resume pointer.
- Audit rows preserve reconstruction identifiers without renaming or dropping payload keys.
- No change to `src/btwin/core/audit.py` is required for this contract.

## What this phase does not guarantee

- full workflow scheduling or dispatch decisions
- retry thresholds or escalation policy
- automatic replay of side effects
- semantic interpretation of audit payloads beyond identifier preservation

Those belong to higher-level workflow recovery logic built on top of this foundation.
