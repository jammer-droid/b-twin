import hashlib

from btwin.core.indexer import CoreIndexer


def _sha256_for(path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def test_refresh_indexes_pending_docs(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="hello convo", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )

    result = idx.refresh(limit=10)

    assert result["indexed"] == 1
    summary = idx.status_summary()
    assert summary.get("indexed", 0) >= 1


def test_reconcile_marks_missing_docs_deleted(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)
    entry = idx.storage.save_convo_record(content="to be deleted", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )
    idx.refresh()

    file_path.unlink()

    idx.reconcile()
    item = idx.manifest.get(rel)
    assert item is not None
    assert item.status == "deleted"


def test_repair_recovers_failed_document(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)
    entry = idx.storage.save_convo_record(content="repair me", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )
    idx.manifest.mark_status(rel, "failed", error="embedding timeout")

    result = idx.repair(rel)

    assert result["ok"] is True
    assert result["status"] == "indexed"


def test_repair_targets_specific_doc_even_with_other_pending_items(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)

    pending_entry = idx.storage.save_convo_record(content="pending", requested_by_user=True)
    target_entry = idx.storage.save_convo_record(content="target", requested_by_user=True)

    pending_path = idx.storage.convo_entries_dir / pending_entry.date / f"{pending_entry.slug}.md"
    target_path = idx.storage.convo_entries_dir / target_entry.date / f"{target_entry.slug}.md"

    pending_rel = str(pending_path.relative_to(tmp_path))
    target_rel = str(target_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=pending_rel,
        path=pending_rel,
        record_type="convo",
        checksum=_sha256_for(pending_path),
    )
    idx.mark_pending(
        doc_id=target_rel,
        path=target_rel,
        record_type="convo",
        checksum=_sha256_for(target_path),
    )
    idx.manifest.mark_status(target_rel, "failed", error="embedding timeout")

    result = idx.repair(target_rel)

    assert result["ok"] is True
    assert idx.manifest.get(target_rel).status == "indexed"
