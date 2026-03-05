from pathlib import Path

from btwin.core.indexer_manifest import IndexManifest


def test_manifest_upsert_and_load(tmp_path: Path) -> None:
    manifest_path = tmp_path / "index_manifest.yaml"
    manifest = IndexManifest(manifest_path)

    manifest.upsert(
        doc_id="d1",
        path="entries/convo/2026-03-05/convo-1.md",
        record_type="convo",
        checksum="sha256:a",
        status="pending",
        doc_version=1,
    )

    reloaded = IndexManifest(manifest_path)
    item = reloaded.get("d1")

    assert item is not None
    assert item.status == "pending"


def test_mark_status_list_and_summary(tmp_path: Path) -> None:
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")

    manifest.upsert(
        doc_id="d1",
        path="entries/convo/2026-03-05/convo-1.md",
        record_type="convo",
        checksum="sha256:a",
        status="pending",
        doc_version=1,
    )
    manifest.upsert(
        doc_id="d2",
        path="entries/entry/2026-03-05/entry-2.md",
        record_type="entry",
        checksum="sha256:b",
        status="indexed",
        doc_version=1,
    )

    updated = manifest.mark_status("d1", "indexed")

    indexed = manifest.list_by_status("indexed")
    summary = manifest.summary()

    assert updated.status == "indexed"
    assert sorted(item.doc_id for item in indexed) == ["d1", "d2"]
    assert summary["total"] == 2
    assert summary["indexed"] == 2
