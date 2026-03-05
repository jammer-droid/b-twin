import pytest

from btwin.core.indexer_manifest import IndexManifest


def test_manifest_upsert_and_load(tmp_path):
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")
    manifest.upsert(
        doc_id="d1",
        path="entries/convo/2026-03-05/convo-1.md",
        record_type="convo",
        checksum="sha256:a",
        status="pending",
    )

    reloaded = IndexManifest(tmp_path / "index_manifest.yaml")
    item = reloaded.get("d1")

    assert item is not None
    assert item.status == "pending"
    assert item.doc_version == 1


def test_manifest_increments_version_when_checksum_changes(tmp_path):
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")
    first = manifest.upsert(
        doc_id="d1",
        path="entries/collab/2026-03-05/collab-1.md",
        record_type="collab",
        checksum="sha256:a",
        status="pending",
    )
    second = manifest.upsert(
        doc_id="d1",
        path="entries/collab/2026-03-05/collab-1.md",
        record_type="collab",
        checksum="sha256:b",
        status="stale",
    )

    assert first.doc_version == 1
    assert second.doc_version == 2


def test_manifest_mark_status_and_summary(tmp_path):
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")
    manifest.upsert(
        doc_id="d1",
        path="entries/entry/2026-03-05/note-1.md",
        record_type="entry",
        checksum="sha256:a",
        status="pending",
    )
    manifest.mark_status("d1", "indexed")

    indexed = manifest.list_by_status("indexed")
    assert len(indexed) == 1

    summary = manifest.summary()
    assert summary["total"] == 1
    assert summary["indexed"] == 1


def test_manifest_mark_status_nonexistent_doc_id(tmp_path):
    """mark_status with a nonexistent doc_id should raise ValueError with clear message."""
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")

    with pytest.raises(ValueError, match="doc_id 'nonexistent' not found in index manifest"):
        manifest.mark_status("nonexistent", "indexed")
