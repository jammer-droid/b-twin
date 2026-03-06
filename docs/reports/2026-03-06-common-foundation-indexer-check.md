# Common foundation indexer compatibility check

## What was reused unchanged

- `Storage._index_doc_info()` still produces the canonical `doc_id`, relative `path`, and checksum payload used by the indexer.
- Existing entry, convo, collab, and promoted document iteration logic stayed intact.
- `CoreIndexer` itself did not require changes for this task because the compatibility check here only needed storage-side enumeration of the new shared/workflow namespace.

## What changed

- Added `Storage.save_shared_record(...)` to persist common-foundation documents under a deterministic path:
  - `entries/shared/<namespace>/<YYYY-MM-DD>/<record_id>.md`
- Added `entries/shared` handling to `Storage.list_indexable_documents()`.
- Shared namespace docs now derive `record_type` from frontmatter `recordType` first, with namespace as a fallback.
- Added `shared` to the storage framework directory skip list so general entry listing does not treat the namespace as dated entry content.

## Verified behavior

- Shared workflow docs are saved to deterministic paths.
- Shared workflow docs appear in `list_indexable_documents()`.
- Workflow docs expose a stable `record_type` of `workflow`, which is suitable for downstream filtering.
- Existing convo/collab/indexer tests still pass after the storage change.

## Future work

- If future workflow indexing flows call `CoreIndexer.mark_pending()` directly with new record types, `RecordType` modeling may need to expand beyond the current literal set.
- Workflow-specific storage helpers (`save_workflow_epic`, `save_workflow_task`, `save_workflow_task_run`, etc.) can build on top of the shared namespace/path convention added here.
