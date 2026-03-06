import pytest
from pydantic import ValidationError

from btwin.core.common_record_models import CommonRecordMetadata


def _valid_payload() -> dict:
    return {
        "docVersion": 1,
        "status": "active",
        "createdAt": "2026-03-06T10:00:00+09:00",
        "updatedAt": "2026-03-06T10:05:00+09:00",
        "recordType": "workflow",
    }


def test_common_record_metadata_accepts_shared_contract_fields() -> None:
    record = CommonRecordMetadata.model_validate(_valid_payload())

    assert record.doc_version == 1
    assert record.status == "active"
    assert record.created_at.isoformat() == "2026-03-06T10:00:00+09:00"
    assert record.updated_at.isoformat() == "2026-03-06T10:05:00+09:00"
    assert record.record_type == "workflow"


def test_common_record_metadata_rejects_naive_timestamps() -> None:
    payload = _valid_payload()
    payload["createdAt"] = "2026-03-06T10:00:00"

    with pytest.raises(ValidationError):
        CommonRecordMetadata.model_validate(payload)
