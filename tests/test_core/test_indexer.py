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


def test_refresh_recomputes_checksum_before_indexing_backlog_doc(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)
    entry = idx.storage.save_convo_record(content="v1", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )

    file_path.write_text("---\ndate: 2026-03-05\nslug: edited\nrecordType: convo\nrequestedByUser: true\ncreated_at: 2026-03-05T00:00:00+00:00\n---\n\nv2\n")
    new_checksum = _sha256_for(file_path)

    idx.refresh(limit=10)

    item = idx.manifest.get(rel)
    assert item is not None
    assert item.status == "indexed"
    assert item.checksum == new_checksum
    assert item.doc_version == 2


def test_kpi_summary_reports_sync_gap_and_repair_metrics(tmp_path, monkeypatch):
    idx = CoreIndexer(data_dir=tmp_path)
    ok_entry = idx.storage.save_convo_record(content="repair ok", requested_by_user=True)
    fail_entry = idx.storage.save_convo_record(content="repair fail", requested_by_user=True)

    ok_path = idx.storage.convo_entries_dir / ok_entry.date / f"{ok_entry.slug}.md"
    fail_path = idx.storage.convo_entries_dir / fail_entry.date / f"{fail_entry.slug}.md"
    ok_rel = str(ok_path.relative_to(tmp_path))
    fail_rel = str(fail_path.relative_to(tmp_path))

    idx.mark_pending(doc_id=ok_rel, path=ok_rel, record_type="convo", checksum=_sha256_for(ok_path))
    idx.mark_pending(doc_id=fail_rel, path=fail_rel, record_type="convo", checksum=_sha256_for(fail_path))
    idx.refresh(limit=10)

    idx.manifest.mark_status(ok_rel, "failed", error="retry")
    idx.manifest.mark_status(fail_rel, "failed", error="retry")

    original_add = idx.vector_store.add

    def fail_once(*args, **kwargs):
        doc_id = kwargs.get("doc_id") if kwargs else None
        if doc_id is None and args:
            doc_id = args[0]
        if doc_id == fail_rel:
            raise RuntimeError("embedding timeout")
        return original_add(*args, **kwargs)

    monkeypatch.setattr(idx.vector_store, "add", fail_once)

    ok_result = idx.repair(ok_rel)
    fail_result = idx.repair(fail_rel)

    assert ok_result["ok"] is True
    assert fail_result["ok"] is False

    idx.vector_store.delete(ok_rel)

    kpi = idx.kpi_summary()

    assert kpi["manifest_vector_mismatch_count"] >= 1
    assert kpi["write_to_indexed_latency_ms_avg"] is not None
    assert kpi["repair_success_rate"] == 0.5
    assert kpi["repair_avg_duration_ms"] >= 0.0
