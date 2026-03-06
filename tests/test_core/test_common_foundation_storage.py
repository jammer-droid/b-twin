from pathlib import Path

from btwin.core.models import Entry
from btwin.core.storage import Storage


def _workflow_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "docVersion": 1,
        "status": "draft",
        "createdAt": "2026-03-06T10:00:00+09:00",
        "updatedAt": "2026-03-06T10:05:00+09:00",
        "recordType": "workflow",
        "title": "Common foundation workflow doc",
    }
    metadata.update(overrides)
    return metadata


def test_save_shared_workflow_doc_uses_deterministic_path(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    path = storage.save_shared_record(
        namespace="workflow",
        record_id="epic-001",
        content="workflow body",
        metadata=_workflow_metadata(),
    )

    assert path == tmp_path / "entries" / "shared" / "workflow" / "2026-03-06" / "epic-001.md"
    assert path.exists()


def test_shared_workflow_docs_are_listed_as_indexable_documents(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    saved_path = storage.save_shared_record(
        namespace="workflow",
        record_id="epic-001",
        content="workflow body",
        metadata=_workflow_metadata(),
    )

    docs = storage.list_indexable_documents()

    workflow_doc = next(
        doc for doc in docs if doc["path"] == saved_path.relative_to(tmp_path).as_posix()
    )
    assert workflow_doc["doc_id"] == "entries/shared/workflow/2026-03-06/epic-001.md"
    assert workflow_doc["record_type"] == "workflow"
    assert workflow_doc["checksum"].startswith("sha256:")


def test_shared_workflow_record_type_is_stable_and_filterable(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.save_entry(
        Entry(
            date="2026-03-06",
            slug="daily-note",
            content="plain entry",
            metadata={"recordType": "entry"},
        )
    )
    storage.save_shared_record(
        namespace="workflow",
        record_id="epic-001",
        content="workflow body v1",
        metadata=_workflow_metadata(),
    )
    storage.save_shared_record(
        namespace="workflow",
        record_id="epic-001",
        content="workflow body v2",
        metadata=_workflow_metadata(status="active", updatedAt="2026-03-06T10:15:00+09:00"),
    )

    workflow_docs = [
        doc for doc in storage.list_indexable_documents() if doc["record_type"] == "workflow"
    ]

    assert len(workflow_docs) == 1
    assert workflow_docs[0]["path"] == "entries/shared/workflow/2026-03-06/epic-001.md"
