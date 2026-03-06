"""Tests for project metadata support in the indexer."""

import hashlib

from btwin.core.indexer import CoreIndexer
from btwin.core.indexer_models import IndexEntry


def _sha256_for(path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# IndexEntry model
# ---------------------------------------------------------------------------

def test_index_entry_has_project_field():
    """IndexEntry accepts project: str | None with default None."""
    entry = IndexEntry(
        doc_id="d1",
        path="entries/_global/2026-03-06/d1.md",
        record_type="entry",
        checksum="sha256:abc",
        status="pending",
        doc_version=1,
    )
    assert entry.project is None

    entry_with_proj = IndexEntry(
        doc_id="d2",
        path="entries/myproj/2026-03-06/d2.md",
        record_type="entry",
        checksum="sha256:abc",
        status="pending",
        project="myproj",
        doc_version=1,
    )
    assert entry_with_proj.project == "myproj"


# ---------------------------------------------------------------------------
# mark_pending stores project
# ---------------------------------------------------------------------------

def test_mark_pending_stores_project(tmp_path):
    """mark_pending(..., project='myproj') stores project in manifest entry."""
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="hello", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    result = idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
        project="myproj",
    )

    assert result.project == "myproj"
    # Verify persistence via manifest.get
    stored = idx.manifest.get(rel)
    assert stored is not None
    assert stored.project == "myproj"


def test_mark_pending_defaults_project_to_none(tmp_path):
    """mark_pending without project defaults to None (backward compat)."""
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="hello", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    result = idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )

    assert result.project is None


# ---------------------------------------------------------------------------
# refresh sends project in vector metadata
# ---------------------------------------------------------------------------

def test_refresh_includes_project_in_vector_metadata(tmp_path, monkeypatch):
    """refresh() passes 'project' field in metadata to vector_store.add()."""
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="project doc", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
        project="alpha",
    )

    captured_metadata: list[dict] = []
    original_add = idx.vector_store.add

    def spy_add(*, doc_id, content, metadata=None):
        captured_metadata.append(metadata)
        return original_add(doc_id=doc_id, content=content, metadata=metadata)

    monkeypatch.setattr(idx.vector_store, "add", spy_add)

    idx.refresh(limit=10)

    assert len(captured_metadata) == 1
    assert captured_metadata[0]["project"] == "alpha"


def test_refresh_defaults_project_to_global_in_metadata(tmp_path, monkeypatch):
    """refresh() defaults project to '_global' in vector metadata when project is None."""
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="global doc", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
    )

    captured_metadata: list[dict] = []
    original_add = idx.vector_store.add

    def spy_add(*, doc_id, content, metadata=None):
        captured_metadata.append(metadata)
        return original_add(doc_id=doc_id, content=content, metadata=metadata)

    monkeypatch.setattr(idx.vector_store, "add", spy_add)

    idx.refresh(limit=10)

    assert len(captured_metadata) == 1
    assert captured_metadata[0]["project"] == "_global"


# ---------------------------------------------------------------------------
# reconcile passes project from storage
# ---------------------------------------------------------------------------

def test_reconcile_preserves_project_from_storage(tmp_path):
    """reconcile() picks up project key from list_indexable_documents."""
    idx = CoreIndexer(data_dir=tmp_path)

    # Save an entry -- storage puts it under _global by default
    entry = idx.storage.save_convo_record(content="reconcile me", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.reconcile()

    item = idx.manifest.get(rel)
    assert item is not None
    # Storage returns project="_global" for default convo entries
    assert item.project == "_global"


# ---------------------------------------------------------------------------
# status_summary with project filter
# ---------------------------------------------------------------------------

def test_status_summary_filters_by_project(tmp_path):
    """status_summary(project='X') counts only that project's docs."""
    idx = CoreIndexer(data_dir=tmp_path)

    # Create docs and mark them pending with different projects
    for i, proj in enumerate(["alpha", "alpha", "beta"]):
        entry = idx.storage.save_convo_record(
            content=f"doc {i}", requested_by_user=True
        )
        file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
        rel = str(file_path.relative_to(tmp_path))
        idx.mark_pending(
            doc_id=rel,
            path=rel,
            record_type="convo",
            checksum=_sha256_for(file_path),
            project=proj,
        )

    alpha_summary = idx.status_summary(project="alpha")
    assert alpha_summary["total"] == 2
    assert alpha_summary["pending"] == 2

    beta_summary = idx.status_summary(project="beta")
    assert beta_summary["total"] == 1
    assert beta_summary["pending"] == 1


def test_status_summary_without_project_counts_all(tmp_path):
    """status_summary(project=None) counts all docs (backward compat)."""
    idx = CoreIndexer(data_dir=tmp_path)

    for i, proj in enumerate(["alpha", "beta", None]):
        entry = idx.storage.save_convo_record(
            content=f"doc {i}", requested_by_user=True
        )
        file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
        rel = str(file_path.relative_to(tmp_path))
        idx.mark_pending(
            doc_id=rel,
            path=rel,
            record_type="convo",
            checksum=_sha256_for(file_path),
            project=proj,
        )

    all_summary = idx.status_summary()
    assert all_summary["total"] == 3

    # Explicit project=None also returns all
    all_summary2 = idx.status_summary(project=None)
    assert all_summary2["total"] == 3


# ---------------------------------------------------------------------------
# failure_queue with project filter
# ---------------------------------------------------------------------------

def test_failure_queue_filters_by_project(tmp_path):
    """failure_queue(project='X') returns only that project's failures."""
    idx = CoreIndexer(data_dir=tmp_path)

    rels_alpha: list[str] = []
    rels_beta: list[str] = []

    for i in range(3):
        entry = idx.storage.save_convo_record(
            content=f"alpha fail {i}", requested_by_user=True
        )
        file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
        rel = str(file_path.relative_to(tmp_path))
        idx.mark_pending(
            doc_id=rel,
            path=rel,
            record_type="convo",
            checksum=_sha256_for(file_path),
            project="alpha",
        )
        idx.manifest.mark_status(rel, "failed", error=f"err alpha {i}")
        rels_alpha.append(rel)

    for i in range(2):
        entry = idx.storage.save_convo_record(
            content=f"beta fail {i}", requested_by_user=True
        )
        file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
        rel = str(file_path.relative_to(tmp_path))
        idx.mark_pending(
            doc_id=rel,
            path=rel,
            record_type="convo",
            checksum=_sha256_for(file_path),
            project="beta",
        )
        idx.manifest.mark_status(rel, "failed", error=f"err beta {i}")
        rels_beta.append(rel)

    alpha_failures = idx.failure_queue(project="alpha")
    assert len(alpha_failures) == 3
    assert all(item["doc_id"] in rels_alpha for item in alpha_failures)

    beta_failures = idx.failure_queue(project="beta")
    assert len(beta_failures) == 2
    assert all(item["doc_id"] in rels_beta for item in beta_failures)

    # No filter returns all
    all_failures = idx.failure_queue()
    assert len(all_failures) == 5


def test_failure_queue_no_project_returns_all(tmp_path):
    """failure_queue(project=None) returns failures from all projects (backward compat)."""
    idx = CoreIndexer(data_dir=tmp_path)

    for i, proj in enumerate(["alpha", "beta", None]):
        entry = idx.storage.save_convo_record(
            content=f"fail {i}", requested_by_user=True
        )
        file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
        rel = str(file_path.relative_to(tmp_path))
        idx.mark_pending(
            doc_id=rel,
            path=rel,
            record_type="convo",
            checksum=_sha256_for(file_path),
            project=proj,
        )
        idx.manifest.mark_status(rel, "failed", error=f"error {i}")

    all_failures = idx.failure_queue(project=None)
    assert len(all_failures) == 3


# ---------------------------------------------------------------------------
# kpi_summary backward compat
# ---------------------------------------------------------------------------

def test_kpi_summary_still_works(tmp_path):
    """kpi_summary() returns valid results after project changes (backward compat)."""
    idx = CoreIndexer(data_dir=tmp_path)

    entry = idx.storage.save_convo_record(content="kpi doc", requested_by_user=True)
    file_path = idx.storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = str(file_path.relative_to(tmp_path))

    idx.mark_pending(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(file_path),
        project="myproj",
    )
    idx.refresh(limit=10)

    kpi = idx.kpi_summary()

    assert "write_to_indexed_latency_ms_avg" in kpi
    assert "manifest_vector_mismatch_count" in kpi
    assert "repair_success_rate" in kpi
    assert "repair_avg_duration_ms" in kpi
    assert kpi["manifest_vector_mismatch_count"] == 0
