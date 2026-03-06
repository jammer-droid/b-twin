from pathlib import Path

import yaml

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

    assert "entries/_global/collab/2026-03-05" in str(path)
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


# --- Fix I17: task_id path sanitization tests ---


def _record_with_task_id(task_id: str, **kwargs: object) -> CollabRecord:
    data = {
        "recordId": "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
        "taskId": task_id,
        "recordType": "collab",
        "summary": "test summary",
        "evidence": ["evidence item"],
        "nextAction": ["next action item"],
        "status": "draft",
        "authorAgent": "test-agent",
        "createdAt": "2026-03-05T15:54:00+09:00",
        "version": 1,
    }
    data.update(kwargs)
    return CollabRecord.model_validate(data)


def test_collab_path_sanitizes_path_traversal(tmp_path: Path) -> None:
    """task_id with ../ should be sanitized to prevent path traversal."""
    storage = Storage(tmp_path)
    record = _record_with_task_id("../../etc/passwd")

    path = storage._collab_path(record)

    # No '..' component should survive in the filename
    assert ".." not in path.name
    # The path must stay under the collab entries directory
    assert str(path).startswith(str(storage.collab_entries_dir))


def test_collab_path_sanitizes_null_bytes(tmp_path: Path) -> None:
    """task_id with null bytes should be sanitized."""
    storage = Storage(tmp_path)
    record = _record_with_task_id("task\x00evil")

    path = storage._collab_path(record)

    assert "\x00" not in path.name
    assert "task-evil" in path.name


def test_collab_path_sanitizes_special_characters(tmp_path: Path) -> None:
    """task_id with special chars like spaces, dots, slashes should be sanitized."""
    storage = Storage(tmp_path)
    record = _record_with_task_id("task/with spaces.and..dots")

    path = storage._collab_path(record)

    # Only alphanumeric, hyphens, and underscores should remain in the task portion
    filename = path.name
    # The filename structure is: {safe_task}-{status}-{record_id}.md
    safe_task = filename.split("-draft-")[0]
    assert all(c.isalnum() or c in ("-", "_") for c in safe_task)


def test_collab_path_preserves_valid_task_id(tmp_path: Path) -> None:
    """Valid task_id with only allowed chars should be unchanged."""
    storage = Storage(tmp_path)
    record = _record_with_task_id("my-task_001")

    path = storage._collab_path(record)

    assert "my-task_001-draft-" in path.name


# --- Fix I15: crash-recovery duplicate file handling tests ---


def _write_collab_file(
    storage: Storage,
    *,
    record_id: str,
    task_id: str,
    status: str,
    version: int,
) -> Path:
    """Write a collab markdown file directly to simulate crash-recovery state."""
    record = CollabRecord.model_validate(
        {
            "recordId": record_id,
            "taskId": task_id,
            "recordType": "collab",
            "summary": f"summary v{version}",
            "evidence": ["evidence"],
            "nextAction": ["action"],
            "status": status,
            "authorAgent": "test-agent",
            "createdAt": "2026-03-05T15:54:00+09:00",
            "version": version,
        }
    )
    return storage.save_collab_record(record)


def test_find_collab_file_prefers_highest_version_on_duplicate(tmp_path: Path) -> None:
    """When duplicate files exist (crash recovery), return the one with highest version."""
    storage = Storage(tmp_path)
    record_id = "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"

    # Simulate crash: both draft (v1) and completed (v2) files exist
    old_path = _write_collab_file(
        storage, record_id=record_id, task_id="task-001", status="draft", version=1
    )
    new_path = _write_collab_file(
        storage, record_id=record_id, task_id="task-001", status="completed", version=2
    )

    # Both files should exist (simulating crash between save and unlink)
    assert old_path.exists()
    assert new_path.exists()
    assert old_path != new_path

    result = storage._find_collab_file(record_id)

    assert result is not None
    record, found_path, _body = result
    assert record.version == 2
    assert record.status == "completed"
    assert found_path == new_path


def test_find_collab_file_handles_single_file(tmp_path: Path) -> None:
    """Normal case: single file returns correctly."""
    storage = Storage(tmp_path)
    record_id = "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"

    _write_collab_file(
        storage, record_id=record_id, task_id="task-001", status="draft", version=1
    )

    result = storage._find_collab_file(record_id)

    assert result is not None
    record, _path, _body = result
    assert record.version == 1
    assert record.status == "draft"


def test_find_collab_file_returns_none_for_missing(tmp_path: Path) -> None:
    """Missing record_id returns None."""
    storage = Storage(tmp_path)

    result = storage._find_collab_file("rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY")

    assert result is None
