from pathlib import Path

from btwin.core.collab_models import CollabRecord
from btwin.core.storage import Storage


def _record(status: str = "draft", version: int = 1) -> CollabRecord:
    return CollabRecord.model_validate(
        {
            "recordId": "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "E2E 서버 충돌 원인 파악 및 수정",
            "evidence": ["tsx integration 11/11 pass"],
            "nextAction": ["CI 스크립트 정리"],
            "status": status,
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
            "version": version,
        }
    )


def test_save_collab_record_to_collab_directory(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    path = storage.save_collab_record(_record())

    assert "entries/collab/2026-03-05" in str(path)
    assert path.read_text().startswith("---")


def test_read_collab_record_roundtrip(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    saved = storage.save_collab_record(_record())

    loaded = storage.read_collab_record("rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY")

    assert loaded is not None
    assert loaded.record_id == "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"
    assert loaded.task_id == "jeonse-e2e-001"
    assert saved.exists()


def test_list_collab_records_returns_saved_items(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.save_collab_record(_record())

    items = storage.list_collab_records()

    assert len(items) == 1
    assert items[0].record_id == "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"


def test_update_collab_record_updates_state_and_version(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.save_collab_record(_record(status="draft", version=1))

    updated = storage.update_collab_record(
        "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
        status="completed",
        version=2,
    )

    assert updated is not None
    assert updated.status == "completed"
    assert updated.version == 2

    all_items = storage.list_collab_records()
    assert len(all_items) == 1
    assert all_items[0].status == "completed"


def test_read_collab_record_document_returns_frontmatter_and_content(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.save_collab_record(_record())

    doc = storage.read_collab_record_document("rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY")

    assert doc is not None
    assert doc["frontmatter"]["recordId"] == "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"
    assert "## Evidence" in doc["content"]
