from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_to_project_layout import _add_project_to_frontmatter, migrate


def _create_entry(
    entries_dir: Path,
    *parts: str,
    content: str = "---\nslug: test\n---\n\n# Test\n",
) -> Path:
    path = entries_dir.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_migrate_date_dirs(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(entries, "2026-03-06", "note.md")
    _create_entry(entries, "2026-03-07", "another.md")

    result = migrate(tmp_path)

    assert result["moved"] == 2
    assert not result["skipped"]
    assert (entries / "_global" / "2026-03-06" / "note.md").exists()
    assert (entries / "_global" / "2026-03-07" / "another.md").exists()
    assert not (entries / "2026-03-06").exists()


def test_migrate_convo_dir(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(entries, "convo", "2026-03-06", "convo.md")

    result = migrate(tmp_path)

    assert result["moved"] == 1
    assert (entries / "_global" / "convo" / "2026-03-06" / "convo.md").exists()


def test_migrate_collab_dir(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(entries, "collab", "2026-03-06", "record.md")

    result = migrate(tmp_path)

    assert (entries / "_global" / "collab" / "2026-03-06" / "record.md").exists()


def test_migrate_global_promoted(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(entries, "global", "promoted", "entry.md")

    result = migrate(tmp_path)

    assert (entries / "_global" / "global" / "promoted" / "entry.md").exists()


def test_adds_project_to_frontmatter(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(
        entries,
        "2026-03-06",
        "note.md",
        content="---\nslug: test\ndate: 2026-03-06\n---\n\n# Test\n",
    )

    result = migrate(tmp_path)

    assert result["updated"] >= 1
    text = (entries / "_global" / "2026-03-06" / "note.md").read_text(encoding="utf-8")
    assert "project: _global" in text


def test_skip_if_already_migrated(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    (entries / "_global").mkdir(parents=True)
    _create_entry(entries, "2026-03-06", "note.md")  # This should NOT be moved

    result = migrate(tmp_path)

    assert result["skipped"]
    assert (entries / "2026-03-06" / "note.md").exists()  # Not moved


def test_dry_run_no_changes(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(entries, "2026-03-06", "note.md")

    result = migrate(tmp_path, dry_run=True)

    assert result["moved"] == 1  # Reports what would be moved
    assert not (entries / "_global").exists()  # But doesn't actually move
    assert (entries / "2026-03-06" / "note.md").exists()


def test_no_entries_dir(tmp_path: Path) -> None:
    result = migrate(tmp_path)
    assert len(result["errors"]) > 0


def test_frontmatter_already_has_project(tmp_path: Path) -> None:
    entries = tmp_path / "entries"
    _create_entry(
        entries,
        "2026-03-06",
        "note.md",
        content="---\nslug: test\nproject: myproj\n---\n\n# Test\n",
    )

    result = migrate(tmp_path)

    text = (entries / "_global" / "2026-03-06" / "note.md").read_text(encoding="utf-8")
    assert "project: myproj" in text  # Original project preserved
    assert text.count("project:") == 1  # Not duplicated


def test_add_project_to_frontmatter_no_frontmatter(tmp_path: Path) -> None:
    """Files without frontmatter are left unchanged."""
    f = tmp_path / "no_fm.md"
    f.write_text("# No frontmatter here\n", encoding="utf-8")

    assert _add_project_to_frontmatter(f) is False
    assert f.read_text(encoding="utf-8") == "# No frontmatter here\n"


def test_migrate_mixed_layout(tmp_path: Path) -> None:
    """Date dirs, convo, collab, and global all migrate together."""
    entries = tmp_path / "entries"
    _create_entry(entries, "2026-03-06", "a.md")
    _create_entry(entries, "convo", "2026-03-06", "b.md")
    _create_entry(entries, "collab", "2026-03-06", "c.md")
    _create_entry(entries, "global", "promoted", "d.md")

    result = migrate(tmp_path)

    assert result["moved"] == 4
    assert result["updated"] == 4
    assert not result["errors"]
    assert (entries / "_global" / "2026-03-06" / "a.md").exists()
    assert (entries / "_global" / "convo" / "2026-03-06" / "b.md").exists()
    assert (entries / "_global" / "collab" / "2026-03-06" / "c.md").exists()
    assert (entries / "_global" / "global" / "promoted" / "d.md").exists()
