from pathlib import Path

from typer.testing import CliRunner

from btwin.cli.main import app
from btwin.core.collab_models import CollabRecord
from btwin.core.promotion_store import PromotionStore
from btwin.core.storage import Storage


runner = CliRunner()


def _record() -> CollabRecord:
    return CollabRecord.model_validate(
        {
            "recordId": "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
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


def test_promotion_run_processes_approved_items(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    data_dir = tmp_path / ".btwin"
    storage = Storage(data_dir)
    storage.save_collab_record(_record())

    store = PromotionStore(data_dir / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY", proposed_by="codex-code")
    store.set_status(item.item_id, "approved", actor="main")

    result = runner.invoke(app, ["promotion", "run"])

    assert result.exit_code == 0
    assert "promoted=1" in result.stdout
    assert storage.promoted_entry_exists(item.item_id)
