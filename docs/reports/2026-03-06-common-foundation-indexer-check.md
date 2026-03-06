# Common foundation indexer compatibility check

## What was reused unchanged

- `Storage._index_doc_info()` still produces the canonical `doc_id`, relative `path`, and checksum payload used by the indexer.
- Existing entry, convo, collab, and promoted document iteration logic stayed intact.
- `CoreIndexer.reconcile()` / `refresh()` control flow stayed unchanged; the compatibility fix was at the shared-document record-type boundary consumed by the manifest.

## What changed

- Added `Storage.save_shared_record(...)` to persist common-foundation documents under a deterministic path:
  - `entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md`
- Added `entries/shared` handling to `Storage.list_indexable_documents()`.
- Shared namespace docs now derive `record_type` from frontmatter `recordType` first, with namespace as a fallback.
- Added `shared` to the storage framework directory skip list so general entry listing does not treat the namespace as dated entry content.
- Expanded the indexer manifest `RecordType` literal set to include `workflow`, so shared workflow docs can pass through `reconcile() -> mark_pending() -> manifest.upsert()` without validation errors.
- Added a regression test that saves a shared workflow doc and verifies `CoreIndexer.reconcile()` indexes it successfully.

## Verified behavior

- Shared workflow docs are saved to deterministic paths.
- Shared workflow docs appear in `list_indexable_documents()`.
- Workflow docs expose a stable `record_type` of `workflow`, which is suitable for downstream filtering.
- `CoreIndexer.reconcile()` now succeeds for shared workflow docs and records them in the manifest as `workflow` + `indexed`.
- Existing common-foundation storage and core indexer tests still pass after the fix.

## Future work

- If additional shared namespaces beyond `workflow` need first-class indexer support, extend `RecordType` intentionally instead of allowing arbitrary strings into the manifest.
- Workflow-specific storage helpers (`save_workflow_epic`, `save_workflow_task`, `save_workflow_task_run`, etc.) can build on top of the shared namespace/path convention added here.
