import pytest

from btwin.core.storage import Storage
from btwin.core.models import Entry


def test_save_entry(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-02",
        slug="test-entry",
        content="# Test Entry\n\nThis is a test.",
        metadata={"topic": "test"},
    )
    saved_path = storage.save_entry(entry)
    assert saved_path.exists()
    assert saved_path == tmp_path / "entries" / "2026-03-02" / "test-entry.md"
    raw = saved_path.read_text()
    assert "---" in raw
    assert "# Test Entry" in raw


def test_list_entries(tmp_path):
    storage = Storage(data_dir=tmp_path)
    storage.save_entry(Entry(date="2026-03-02", slug="entry-1", content="# Entry 1"))
    storage.save_entry(Entry(date="2026-03-02", slug="entry-2", content="# Entry 2"))
    storage.save_entry(Entry(date="2026-03-01", slug="entry-3", content="# Entry 3"))
    entries = storage.list_entries()
    assert len(entries) == 3


def test_read_entry(tmp_path):
    storage = Storage(data_dir=tmp_path)
    storage.save_entry(Entry(date="2026-03-02", slug="read-test", content="# Read Test"))
    entry = storage.read_entry("2026-03-02", "read-test")
    assert entry is not None
    assert "# Read Test" in entry.content
    assert "---" not in entry.content  # frontmatter stripped


def test_read_nonexistent_entry(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = storage.read_entry("2026-03-02", "nonexistent")
    assert entry is None


def test_save_entry_with_frontmatter(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-02",
        slug="fm-test",
        content="# Frontmatter Test\n\nSome content.",
        metadata={"topic": "test", "created_at": "2026-03-02T00:00:00+00:00"},
    )
    saved_path = storage.save_entry(entry)
    raw = saved_path.read_text()
    assert raw.startswith("---\n")
    assert "date: '2026-03-02'" in raw or "date: 2026-03-02" in raw
    assert "slug: fm-test" in raw
    assert "topic: test" in raw
    assert "---" in raw
    assert "# Frontmatter Test" in raw


def test_read_entry_parses_frontmatter(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-02",
        slug="parse-test",
        content="# Parse Test\n\nBody text.",
        metadata={"topic": "career"},
    )
    storage.save_entry(entry)
    loaded = storage.read_entry("2026-03-02", "parse-test")
    assert loaded is not None
    assert loaded.metadata["topic"] == "career"
    assert loaded.metadata["date"] == "2026-03-02"
    assert loaded.metadata["slug"] == "parse-test"
    assert "# Parse Test" in loaded.content
    assert "---" not in loaded.content  # frontmatter stripped from content


def test_list_entries_parses_frontmatter(tmp_path):
    storage = Storage(data_dir=tmp_path)
    storage.save_entry(Entry(
        date="2026-03-02",
        slug="list-test",
        content="# List Test",
        metadata={"topic": "study"},
    ))
    entries = storage.list_entries()
    assert len(entries) == 1
    assert entries[0].metadata["topic"] == "study"
    assert "---" not in entries[0].content


def test_read_entry_without_frontmatter(tmp_path):
    """Backwards compatibility: read old entries without frontmatter."""
    storage = Storage(data_dir=tmp_path)
    # Manually write a file without frontmatter (old format)
    date_dir = tmp_path / "entries" / "2026-03-01"
    date_dir.mkdir(parents=True)
    (date_dir / "old-entry.md").write_text("# Old Entry\n\nNo frontmatter.")
    entry = storage.read_entry("2026-03-01", "old-entry")
    assert entry is not None
    assert entry.content == "# Old Entry\n\nNo frontmatter."
    assert entry.metadata == {}


def test_read_entry_preserves_structured_frontmatter(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-03",
        slug="graph-note",
        content="# Graph Note\n\nBody",
        metadata={
            "topic": "memory",
            "tags": ["ux", "dashboard"],
            "related": ["2026-03-01-note-1", "2026-03-02-note-9"],
            "importance": "high",
        },
    )
    storage.save_entry(entry)

    loaded = storage.read_entry("2026-03-03", "graph-note")
    assert loaded is not None
    assert loaded.metadata["tags"] == ["ux", "dashboard"]
    assert loaded.metadata["related"] == ["2026-03-01-note-1", "2026-03-02-note-9"]
    assert loaded.metadata["importance"] == "high"


def test_save_entry_merges_on_collision(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry1 = Entry(
        date="2026-03-02",
        slug="merge-test",
        content="# First\n\nFirst content.",
        metadata={"tags": ["alpha"]},
    )
    entry2 = Entry(
        date="2026-03-02",
        slug="merge-test",
        content="Second content.",
        metadata={"tags": ["beta"]},
    )
    storage.save_entry(entry1)
    storage.save_entry(entry2)

    loaded = storage.read_entry("2026-03-02", "merge-test")
    assert loaded is not None
    assert "First content." in loaded.content
    assert "Second content." in loaded.content
    assert "---" in loaded.content
    assert set(loaded.metadata["tags"]) == {"alpha", "beta"}


def test_save_entry_merges_tags_union(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry1 = Entry(
        date="2026-03-02",
        slug="tag-merge",
        content="Content A",
        metadata={"tags": ["a", "b"]},
    )
    entry2 = Entry(
        date="2026-03-02",
        slug="tag-merge",
        content="Content B",
        metadata={"tags": ["b", "c"]},
    )
    storage.save_entry(entry1)
    storage.save_entry(entry2)

    loaded = storage.read_entry("2026-03-02", "tag-merge")
    assert set(loaded.metadata["tags"]) == {"a", "b", "c"}


def test_save_entry_no_collision_works_as_before(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-02",
        slug="no-collision",
        content="# New\n\nBrand new entry.",
        metadata={"topic": "test"},
    )
    saved_path = storage.save_entry(entry)
    assert saved_path.exists()
    loaded = storage.read_entry("2026-03-02", "no-collision")
    assert loaded.content == "# New\n\nBrand new entry."


def test_save_convo_record_rejects_invalid_contract(tmp_path, monkeypatch):
    storage = Storage(data_dir=tmp_path)

    monkeypatch.setattr(
        "btwin.core.storage.validate_document_contract",
        lambda record_type, metadata: (False, "forced invalid contract"),
    )

    with pytest.raises(ValueError, match="invalid convo contract"):
        storage.save_convo_record(content="hello", requested_by_user=True)
