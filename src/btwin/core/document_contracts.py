"""Document contract registry and first-pass metadata validation."""

from __future__ import annotations

from types import MappingProxyType

_REQUIRED_KEYS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "entry": ("date", "slug"),
        "convo": ("recordType", "requestedByUser"),
        "collab": ("recordId", "taskId", "recordType", "status", "authorAgent", "createdAt"),
        "promoted": ("promotionItemId", "sourceRecordId", "scope"),
    }
)


def validate_document_contract(record_type: str, metadata: dict[str, object]) -> tuple[bool, str]:
    required = _REQUIRED_KEYS.get(record_type)
    if required is None:
        return False, f"unknown record_type: {record_type}"

    missing = [key for key in required if key not in metadata]
    if missing:
        return False, f"missing required metadata keys: {', '.join(missing)}"

    return True, ""
