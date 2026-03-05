from pathlib import Path

from btwin.core.collab_models import CollabRecord
from btwin.core.indexer import CoreIndexer
from btwin.core.promotion_store import PromotionStore
from btwin.core.promotion_worker import PromotionWorker
from btwin.core.storage import Storage


def _collab_record(record_id: str = "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY") -> CollabRecord:
    return CollabRecord.model_validate(
        {
            "recordId": record_id,
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "E2E 서버 충돌 원인 파악 및 수정",
            "evidence": ["tsx integration 11/11 pass"],
            "nextAction": ["CI 스크립트 정리"],
            "status": "completed",
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
            "version": 3,
        }
    )


def test_worker_promotes_approved_items_to_global(tmp_path: Path):
    storage = Storage(tmp_path)
    promotion_store = PromotionStore(tmp_path / "promotion_queue.yaml")

    source = _collab_record()
    storage.save_collab_record(source)

    item = promotion_store.enqueue(source_record_id=source.record_id, proposed_by="codex-code")
    promotion_store.set_status(item.item_id, "approved", actor="main")

    worker = PromotionWorker(storage=storage, promotion_store=promotion_store)
    result = worker.run_once()

    assert result["promoted"] == 1
    refreshed = promotion_store.list_items(status="promoted")
    assert len(refreshed) == 1
    assert storage.promoted_entry_exists(item.item_id)


def test_worker_is_idempotent_on_rerun(tmp_path: Path):
    storage = Storage(tmp_path)
    promotion_store = PromotionStore(tmp_path / "promotion_queue.yaml")

    source = _collab_record()
    storage.save_collab_record(source)

    item = promotion_store.enqueue(source_record_id=source.record_id, proposed_by="codex-code")
    promotion_store.set_status(item.item_id, "approved", actor="main")

    worker = PromotionWorker(storage=storage, promotion_store=promotion_store)
    first = worker.run_once()
    second = worker.run_once()

    assert first["promoted"] == 1
    assert second["promoted"] == 0
    assert storage.count_promoted_entries() == 1


def test_worker_recovers_orphaned_queued_item(tmp_path: Path):
    """A queued item (from a previous run that failed mid-save) is retried."""
    storage = Storage(tmp_path)
    promotion_store = PromotionStore(tmp_path / "promotion_queue.yaml")

    source = _collab_record()
    storage.save_collab_record(source)

    # Simulate a previous run that transitioned the item to "queued" but
    # crashed before save_promoted_entry completed (orphaned queued item).
    item = promotion_store.enqueue(source_record_id=source.record_id, proposed_by="codex-code")
    promotion_store.set_status(item.item_id, "approved", actor="main")
    promotion_store.set_status(item.item_id, "queued", actor="main")

    # The promoted entry does NOT exist — the previous run failed mid-save.
    assert not storage.promoted_entry_exists(item.item_id)

    worker = PromotionWorker(storage=storage, promotion_store=promotion_store)
    result = worker.run_once()

    assert result["promoted"] == 1
    assert result["errors"] == 0
    refreshed = promotion_store.list_items(status="promoted")
    assert len(refreshed) == 1
    assert storage.promoted_entry_exists(item.item_id)


def test_worker_skips_missing_source_record(tmp_path: Path):
    storage = Storage(tmp_path)
    promotion_store = PromotionStore(tmp_path / "promotion_queue.yaml")

    item = promotion_store.enqueue(source_record_id="rec_missing", proposed_by="codex-code")
    promotion_store.set_status(item.item_id, "approved", actor="main")

    worker = PromotionWorker(storage=storage, promotion_store=promotion_store)
    result = worker.run_once()

    assert result["errors"] == 1
    approved = promotion_store.list_items(status="approved")
    assert len(approved) == 1


def test_promoted_entry_is_vector_indexed(tmp_path: Path):
    """Promoted entries should appear in the vector index after batch promotion."""
    indexer = CoreIndexer(data_dir=tmp_path)
    storage = indexer.storage
    promotion_store = PromotionStore(tmp_path / "promotion_queue.yaml")

    source = _collab_record()
    storage.save_collab_record(source)

    item = promotion_store.enqueue(source_record_id=source.record_id, proposed_by="codex-code")
    promotion_store.set_status(item.item_id, "approved", actor="main")

    worker = PromotionWorker(storage=storage, promotion_store=promotion_store, indexer=indexer)
    result = worker.run_once()

    assert result["promoted"] == 1

    # The promoted entry must be in the index manifest as "indexed".
    expected_rel = (
        storage.promoted_entries_dir / "promoted" / f"{item.item_id}.md"
    ).relative_to(tmp_path).as_posix()
    manifest_entry = indexer.manifest.get(expected_rel)
    assert manifest_entry is not None, f"Expected manifest entry for {expected_rel}"
    assert manifest_entry.status == "indexed"
    assert manifest_entry.record_type == "promoted"

    # The content should be searchable in the vector store.
    results = indexer.vector_store.search("서버 충돌", n_results=5)
    doc_ids = [r["id"] for r in results]
    assert expected_rel in doc_ids, f"Promoted entry {expected_rel} not found in vector search results"
