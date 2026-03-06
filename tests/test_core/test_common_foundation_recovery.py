import json
from pathlib import Path

import pytest
import yaml

from btwin.core.audit import AuditLogger
from btwin.core.storage import Storage


def _workflow_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "recordId": "task-run-001",
        "docVersion": 1,
        "status": "queued",
        "createdAt": "2026-03-06T10:00:00+09:00",
        "updatedAt": "2026-03-06T10:00:00+09:00",
        "recordType": "workflow",
        "title": "Common foundation workflow run",
    }
    metadata.update(overrides)
    return metadata


def _read_frontmatter(file_path: Path) -> dict[str, object]:
    raw = file_path.read_text(encoding="utf-8")
    parts = raw.split("---\n", 2)
    assert len(parts) == 3
    return yaml.safe_load(parts[1]) or {}


def _compute_resume_pointer(*, data_dir: Path, file_path: Path) -> dict[str, object]:
    storage = Storage(data_dir)
    indexed_docs = {
        doc["path"]: doc
        for doc in storage.list_indexable_documents()
    }
    relative_path = file_path.relative_to(data_dir).as_posix()
    frontmatter = _read_frontmatter(file_path)
    indexed = indexed_docs[relative_path]
    return {
        "record_id": frontmatter["recordId"],
        "doc_id": indexed["doc_id"],
        "record_type": indexed["record_type"],
        "doc_version": frontmatter["docVersion"],
        "status": frontmatter["status"],
        "updated_at": frontmatter["updatedAt"],
        "checksum": indexed["checksum"],
    }


def test_persisted_shared_record_state_is_sufficient_to_compute_resume_pointer(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    first_path = storage.save_shared_record(
        namespace="workflow",
        record_id="task-run-001",
        content="queued body",
        metadata=_workflow_metadata(),
    )
    second_path = storage.save_shared_record(
        namespace="workflow",
        record_id="task-run-001",
        content="running body",
        metadata=_workflow_metadata(
            createdAt="2026-03-07T09:00:00+09:00",
            docVersion=2,
            status="running",
            updatedAt="2026-03-07T09:15:00+09:00",
        ),
    )

    assert first_path == second_path == tmp_path / "entries" / "shared" / "workflow" / "2026-03-06" / "task-run-001.md"
    assert [
        path.relative_to(tmp_path).as_posix()
        for path in sorted(tmp_path.glob("entries/shared/workflow/*/task-run-001.md"))
    ] == ["entries/shared/workflow/2026-03-06/task-run-001.md"]

    frontmatter = _read_frontmatter(second_path)
    assert frontmatter["recordId"] == "task-run-001"
    assert frontmatter["createdAt"] == "2026-03-06T10:00:00+09:00"
    assert frontmatter["updatedAt"] == "2026-03-07T09:15:00+09:00"

    resume_pointer = _compute_resume_pointer(data_dir=tmp_path, file_path=second_path)

    assert resume_pointer == {
        "record_id": "task-run-001",
        "doc_id": "entries/shared/workflow/2026-03-06/task-run-001.md",
        "record_type": "workflow",
        "doc_version": 2,
        "status": "running",
        "updated_at": "2026-03-07T09:15:00+09:00",
        "checksum": resume_pointer["checksum"],
    }
    assert str(resume_pointer["checksum"]).startswith("sha256:")


def test_shared_record_storage_synthesizes_and_validates_record_id(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    metadata = _workflow_metadata()
    metadata.pop("recordId")

    file_path = storage.save_shared_record(
        namespace="workflow",
        record_id="task-run-001",
        content="queued body",
        metadata=metadata,
    )

    frontmatter = _read_frontmatter(file_path)
    assert frontmatter["recordId"] == "task-run-001"

    with pytest.raises(ValueError, match="metadata recordId must match record_id"):
        storage.save_shared_record(
            namespace="workflow",
            record_id="task-run-001",
            content="queued body",
            metadata=_workflow_metadata(recordId="task-run-999"),
        )


def test_audit_rows_retain_recovery_identifiers_needed_for_reconstruction(tmp_path: Path) -> None:
    logger = AuditLogger(tmp_path / "audit.log.jsonl")
    recovery_payload = {
        "recordId": "task-run-001",
        "taskRunId": "run-001",
        "docId": "entries/shared/workflow/2026-03-06/task-run-001.md",
        "docVersion": 2,
        "status": "running",
        "resumeReason": "retry_after_restart",
    }

    logger.log(
        event_type="workflow_resume_planned",
        payload=recovery_payload,
        trace_id="trc_recovery0001",
    )

    persisted = json.loads((tmp_path / "audit.log.jsonl").read_text(encoding="utf-8").strip())

    assert persisted["timestamp"]
    assert persisted["eventType"] == "workflow_resume_planned"
    assert persisted["traceId"] == "trc_recovery0001"
    assert persisted["payload"] == recovery_payload
