import hashlib
from pathlib import Path

from typer.testing import CliRunner

from btwin.cli.main import app
from btwin.core.indexer_manifest import IndexManifest
from btwin.core.storage import Storage


runner = CliRunner()


def _sha256_for(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def test_indexer_status_command(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    res = runner.invoke(app, ["indexer", "status"])

    assert res.exit_code == 0
    assert "indexed" in res.output.lower()


def test_indexer_refresh_command_indexes_pending_doc(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data_dir = Path(tmp_path) / ".btwin"

    storage = Storage(data_dir)
    entry = storage.save_convo_record(content="cli refresh", requested_by_user=True)
    path = data_dir / "entries" / "convo" / entry.date / f"{entry.slug}.md"
    rel = path.relative_to(data_dir).as_posix()

    manifest = IndexManifest(data_dir / "index_manifest.yaml")
    manifest.upsert(
        doc_id=rel,
        path=rel,
        record_type="convo",
        checksum=_sha256_for(path),
        status="pending",
    )

    res = runner.invoke(app, ["indexer", "refresh", "--limit", "10"])

    assert res.exit_code == 0
    assert "indexed=1" in res.output
