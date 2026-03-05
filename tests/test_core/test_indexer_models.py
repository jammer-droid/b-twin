import pytest
from pydantic import ValidationError

from btwin.core.indexer_models import IndexEntry


def test_index_entry_requires_core_fields() -> None:
    item = IndexEntry(
        doc_id="entries/convo/2026-03-05/convo-123.md",
        path="entries/convo/2026-03-05/convo-123.md",
        record_type="convo",
        checksum="sha256:abc",
        status="pending",
        doc_version=1,
    )

    assert item.status == "pending"


def test_index_entry_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        IndexEntry(
            doc_id="x",
            path="x",
            record_type="convo",
            checksum="sha256:x",
            status="bad",
            doc_version=1,
        )
