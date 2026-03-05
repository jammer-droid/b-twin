import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app
from btwin.core.indexer_manifest import IndexManifest
from btwin.core.storage import Storage


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(data_dir=tmp_path, initial_agents={"main", "codex-code"}, admin_token="secret")
    return TestClient(app)


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def test_indexer_status_requires_admin_token(tmp_path):
    client = _client(tmp_path)

    denied = client.get("/api/indexer/status")
    assert denied.status_code == 403

    ok = client.get("/api/indexer/status", headers={"X-Admin-Token": "secret"})
    assert ok.status_code == 200
    assert "indexed" in ok.json()


def test_indexer_refresh_indexes_pending_docs(tmp_path):
    client = _client(tmp_path)
    storage = Storage(tmp_path)
    entry = storage.save_convo_record(content="api indexer", requested_by_user=True)
    fpath = storage.convo_entries_dir / entry.date / f"{entry.slug}.md"
    rel = fpath.relative_to(tmp_path).as_posix()

    manifest = IndexManifest(tmp_path / "index_manifest.yaml")
    manifest.upsert(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256(fpath),
        status="pending",
    )

    res = client.post(
        "/api/indexer/refresh",
        json={"actorAgent": "main", "limit": 10},
        headers={"X-Actor-Agent": "main", "X-Admin-Token": "secret"},
    )

    assert res.status_code == 200
    assert res.json()["indexed"] >= 1


def test_indexer_reconcile_endpoint_runs(tmp_path):
    client = _client(tmp_path)

    res = client.post(
        "/api/indexer/reconcile",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main", "X-Admin-Token": "secret"},
    )

    assert res.status_code == 200
    assert "processed" in res.json()
