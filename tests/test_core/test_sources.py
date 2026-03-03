from pathlib import Path

from btwin.core.sources import SourceRegistry


def test_ensure_global_default_creates_source(tmp_path):
    registry = SourceRegistry(tmp_path / "sources.yaml")
    sources = registry.ensure_global_default()

    assert len(sources) == 1
    assert sources[0].name == "global"
    assert Path(sources[0].path).name == ".btwin"


def test_add_source_deduplicates_by_canonical_path(tmp_path):
    data_dir = tmp_path / "project-a" / ".btwin"
    data_dir.mkdir(parents=True)

    registry = SourceRegistry(tmp_path / "sources.yaml")
    one = registry.add_source(data_dir)
    two = registry.add_source(data_dir)

    assert one.path == two.path
    assert len(registry.load()) == 1


def test_scan_for_btwin_dirs_finds_candidates(tmp_path):
    (tmp_path / "playground" / "a" / ".btwin").mkdir(parents=True)
    (tmp_path / "playground" / "b" / ".btwin").mkdir(parents=True)

    found = SourceRegistry.scan_for_btwin_dirs([tmp_path / "playground"], max_depth=4)

    assert tmp_path / "playground" / "a" / ".btwin" in found
    assert tmp_path / "playground" / "b" / ".btwin" in found


def test_scan_for_btwin_dirs_respects_excludes(tmp_path):
    (tmp_path / "playground" / "node_modules" / "x" / ".btwin").mkdir(parents=True)
    (tmp_path / "playground" / "real" / ".btwin").mkdir(parents=True)

    found = SourceRegistry.scan_for_btwin_dirs([tmp_path / "playground"], max_depth=6)

    assert tmp_path / "playground" / "real" / ".btwin" in found
    assert tmp_path / "playground" / "node_modules" / "x" / ".btwin" not in found


def test_refresh_entry_counts_updates_counts_and_timestamps(tmp_path):
    source_dir = tmp_path / "global" / ".btwin"
    (source_dir / "entries" / "2026-03-03").mkdir(parents=True)
    (source_dir / "entries" / "2026-03-03" / "a.md").write_text("# a")
    (source_dir / "entries" / "2026-03-03" / "b.md").write_text("# b")

    registry = SourceRegistry(tmp_path / "sources.yaml")
    registry.add_source(source_dir, name="global")

    updated = registry.refresh_entry_counts()
    assert len(updated) == 1
    assert updated[0].entry_count == 2
    assert updated[0].last_scanned_at is not None
