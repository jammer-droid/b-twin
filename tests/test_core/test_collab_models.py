from datetime import datetime

import pytest
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


@pytest.mark.parametrize("field_name", ["evidence", "nextAction"])
def test_collab_record_rejects_empty_lists(field_name: str) -> None:
    payload = _valid_payload()
    payload[field_name] = []

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_blank_list_items() -> None:
    payload = _valid_payload()
    payload["evidence"] = ["   "]

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_invalid_record_id() -> None:
    payload = _valid_payload()
    payload["recordId"] = "bad-id"

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_u_in_record_id() -> None:
    payload = _valid_payload()
    payload["recordId"] = "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BU"  # U is not in Crockford base32

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_invalid_status() -> None:
    payload = _valid_payload()
    payload["status"] = "in_progress"

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_version_less_than_one() -> None:
    payload = _valid_payload()
    payload["version"] = 0

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_wrong_record_type() -> None:
    payload = _valid_payload()
    payload["recordType"] = "convo"

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_missing_required_field() -> None:
    payload = _valid_payload()
    payload.pop("authorAgent")

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_rejects_naive_created_at() -> None:
    payload = _valid_payload()
    payload["createdAt"] = "2026-03-05T15:54:00"

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


@pytest.mark.parametrize("field_name", ["taskId", "summary", "authorAgent"])
def test_collab_record_rejects_blank_text_fields(field_name: str) -> None:
    payload = _valid_payload()
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_collab_record_strips_text_and_list_items() -> None:
    payload = _valid_payload()
    payload["taskId"] = "  jeonse-e2e-001  "
    payload["summary"] = "  요약  "
    payload["authorAgent"] = "  codex-code  "
    payload["evidence"] = ["  proof  "]
    payload["nextAction"] = ["  next  "]

    record = CollabRecord.model_validate(payload)

    assert record.task_id == "jeonse-e2e-001"
    assert record.summary == "요약"
    assert record.author_agent == "codex-code"
    assert record.evidence == ["proof"]
    assert record.next_action == ["next"]


def test_collab_record_rejects_blank_next_action_item() -> None:
    payload = _valid_payload()
    payload["nextAction"] = ["   "]

    with pytest.raises(ValidationError):
        CollabRecord.model_validate(payload)


def test_generate_record_id_returns_prefixed_ulid_shape() -> None:
    record_id = generate_record_id()

    assert record_id.startswith("rec_")
    assert len(record_id) == 30  # rec_ + 26-char ULID



def test_generate_record_id_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        generate_record_id(datetime(2026, 3, 5, 15, 54, 0))
