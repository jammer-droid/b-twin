from pathlib import Path

from btwin.core.collab_models import CollabRecord
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
