from pydantic import ValidationError

from btwin.core.collab_models import CollabRecord, generate_record_id


def _valid_payload() -> dict:
    return {
        "recordId": "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
        "taskId": "jeonse-e2e-001",
        "recordType": "collab",
        "summary": "E2E 서버 충돌 원인 파악 및 수정",
        "evidence": ["tsx integration 11/11 pass"],
        "nextAction": ["CI 스크립트 정리"],
        "status": "draft",
        "authorAgent": "codex-code",
        "createdAt": "2026-03-05T15:54:00+09:00",
        "version": 1,
    }


def test_collab_record_accepts_schema_b_fields() -> None:
    record = CollabRecord.model_validate(_valid_payload())

    assert record.record_id == "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY"
    assert record.task_id == "jeonse-e2e-001"
    assert record.record_type == "collab"
    assert record.status == "draft"
    assert record.version == 1


def test_collab_record_rejects_empty_evidence() -> None:
    payload = _valid_payload()
    payload["evidence"] = []

    try:
        CollabRecord.model_validate(payload)
        assert False, "expected ValidationError"
    except ValidationError as exc:
        assert "evidence" in str(exc)


def test_collab_record_rejects_empty_next_action() -> None:
    payload = _valid_payload()
    payload["nextAction"] = []

    try:
        CollabRecord.model_validate(payload)
        assert False, "expected ValidationError"
    except ValidationError as exc:
        assert "nextAction" in str(exc)


def test_collab_record_rejects_invalid_record_id() -> None:
    payload = _valid_payload()
    payload["recordId"] = "bad-id"

    try:
        CollabRecord.model_validate(payload)
        assert False, "expected ValidationError"
    except ValidationError as exc:
        assert "recordId" in str(exc)


def test_generate_record_id_returns_prefixed_ulid_shape() -> None:
    record_id = generate_record_id()

    assert record_id.startswith("rec_")
    assert len(record_id) == 30  # rec_ + 26-char ULID
