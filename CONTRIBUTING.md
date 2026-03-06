---
doc_version: 1
---

# Contributing to B-TWIN

## Core reliability rules

Before merge, contributors must preserve the consistency-layer workflow:

1. `mark_pending` before any state-changing path that is not yet fully reconciled
2. `refresh + reconcile` at end-of-batch/session to converge runtime state and docs
3. `repair` for unresolved mismatches, with audit evidence
4. `doc_version` bump for managed docs and specs

## `mark_pending` usage rules

Use `mark_pending` when any of the following applies:

- async/background indexing has not completed
- approval/commit state is not finalized
- source was changed but vector/manifest sync is not yet confirmed
- runtime mode transition is in progress

Do **not** skip pending by directly labeling final success before reconciliation.

## Code review checklist (required)

Reviewers should block merge if any item fails:

- [ ] state transition paths show explicit pending handling (`mark_pending` or equivalent)
- [ ] end-of-batch/session path runs `refresh + reconcile`
- [ ] evidence exists for unresolved mismatch handling (`repair` or documented exception)
- [ ] changed operational/spec docs include `doc_version`
- [ ] tests/check scripts pass in CI or local verification log

## Documentation verification

Run doc version check before opening PR:

```bash
python scripts/doc_version_check.py
```

Optional: verify only specific files.

```bash
python scripts/doc_version_check.py docs/runbook.md docs/indexer-operations.md
```
