"""Tests for project-level path partitioning in Storage."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from btwin.core.collab_models import CollabRecord
from btwin.core.models import Entry
from btwin.core.storage import Storage


def _collab_record(
    record_id: str = "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
    task_id: str = "task-001",
    status: str = "draft",
    version: int = 1,
) -> CollabRecord:
    return CollabRecord.model_validate(
        {
            "recordId": record_id,
            "taskId": task_id,
            "recordType": "collab",
            "summary": "test summary",
            "evidence": ["evidence item"],
            "nextAction": ["next action item"],
            "status": status,
            "authorAgent": "test-agent",
            "createdAt": "2026-03-05T15:54:00+09:00",
            "version": version,
        }
    )


# =============================================================================
# save_entry with project
# =============================================================================


class TestSaveEntryWithProject:
    def test_saves_under_project_directory(self, tmp_path: Path) -> None:
        """save_entry(entry, project='myproj') saves to entries/myproj/{date}/{slug}.md"""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06",
            slug="hello",
            content="# Hello",
            metadata={"topic": "test"},
        )

        path = storage.save_entry(entry, project="myproj")

        expected = tmp_path / "entries" / "myproj" / "2026-03-06" / "hello.md"
        assert path == expected
        assert path.exists()

    def test_defaults_to_global_when_no_project(self, tmp_path: Path) -> None:
        """save_entry(entry, project=None) saves to entries/_global/{date}/{slug}.md"""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06",
            slug="fallback",
            content="# Fallback",
            metadata={"topic": "test"},
        )

        path = storage.save_entry(entry, project=None)

        expected = tmp_path / "entries" / "_global" / "2026-03-06" / "fallback.md"
        assert path == expected
        assert path.exists()

    def test_frontmatter_includes_project_field(self, tmp_path: Path) -> None:
        """Saved file frontmatter must include a 'project' key."""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06",
            slug="fm-proj",
            content="# FM Proj",
            metadata={"topic": "test"},
        )

        path = storage.save_entry(entry, project="myproj")

        raw = path.read_text()
        assert raw.startswith("---\n")
        parts = raw.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["project"] == "myproj"

    def test_frontmatter_project_is_global_when_none(self, tmp_path: Path) -> None:
        """When project is None, frontmatter project should be '_global'."""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06",
            slug="fm-global",
            content="# FM Global",
            metadata={"topic": "test"},
        )

        path = storage.save_entry(entry, project=None)

        raw = path.read_text()
        parts = raw.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["project"] == "_global"

    def test_auto_creates_project_directory(self, tmp_path: Path) -> None:
        """Project directory is auto-created on first write."""
        storage = Storage(tmp_path)
        proj_dir = tmp_path / "entries" / "newproj"
        assert not proj_dir.exists()

        entry = Entry(
            date="2026-03-06", slug="auto", content="# Auto", metadata={"topic": "x"}
        )
        storage.save_entry(entry, project="newproj")

        assert proj_dir.exists()

    def test_merge_works_within_project(self, tmp_path: Path) -> None:
        """Merge-on-collision works when saving to the same project/date/slug."""
        storage = Storage(tmp_path)
        e1 = Entry(
            date="2026-03-06",
            slug="merge",
            content="First",
            metadata={"tags": ["a"]},
        )
        e2 = Entry(
            date="2026-03-06",
            slug="merge",
            content="Second",
            metadata={"tags": ["b"]},
        )
        storage.save_entry(e1, project="proj")
        storage.save_entry(e2, project="proj")

        loaded = storage.read_entry("2026-03-06", "merge", project="proj")
        assert loaded is not None
        assert "First" in loaded.content
        assert "Second" in loaded.content
        assert set(loaded.metadata["tags"]) == {"a", "b"}


# =============================================================================
# list_entries with project
# =============================================================================


class TestListEntriesWithProject:
    def test_list_entries_for_specific_project(self, tmp_path: Path) -> None:
        """list_entries(project='myproj') returns only that project's entries."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="p1", content="# P1", metadata={"topic": "x"}),
            project="myproj",
        )
        storage.save_entry(
            Entry(date="2026-03-06", slug="p2", content="# P2", metadata={"topic": "y"}),
            project="other",
        )

        entries = storage.list_entries(project="myproj")

        assert len(entries) == 1
        assert entries[0].slug == "p1"

    def test_list_entries_none_returns_all_projects(self, tmp_path: Path) -> None:
        """list_entries(project=None) returns ALL entries across all projects."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="a", content="# A", metadata={"topic": "x"}),
            project="proj1",
        )
        storage.save_entry(
            Entry(date="2026-03-06", slug="b", content="# B", metadata={"topic": "y"}),
            project="proj2",
        )
        storage.save_entry(
            Entry(date="2026-03-06", slug="c", content="# C", metadata={"topic": "z"}),
            project=None,  # _global
        )

        entries = storage.list_entries(project=None)

        slugs = {e.slug for e in entries}
        assert slugs == {"a", "b", "c"}

    def test_list_entries_excludes_convo_collab_dirs(self, tmp_path: Path) -> None:
        """list_entries for a project must skip convo/ and collab/ subdirs."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="real", content="# Real", metadata={"topic": "x"}),
            project="myproj",
        )
        # Save convo and collab under same project
        storage.save_convo_record(content="convo", requested_by_user=True, project="myproj")
        storage.save_collab_record(_collab_record(), project="myproj")

        entries = storage.list_entries(project="myproj")

        slugs = [e.slug for e in entries]
        assert slugs == ["real"]


# =============================================================================
# save_convo_record with project
# =============================================================================


class TestSaveConvoRecordWithProject:
    def test_saves_under_project_convo_directory(self, tmp_path: Path) -> None:
        """save_convo_record with project saves to entries/{project}/convo/{date}/."""
        storage = Storage(tmp_path)

        entry = storage.save_convo_record(
            content="remember this",
            requested_by_user=True,
            project="myproj",
        )

        convo_path = (
            tmp_path / "entries" / "myproj" / "convo" / entry.date / f"{entry.slug}.md"
        )
        assert convo_path.exists()

    def test_convo_defaults_to_global(self, tmp_path: Path) -> None:
        """save_convo_record without project saves to entries/_global/convo/{date}/."""
        storage = Storage(tmp_path)

        entry = storage.save_convo_record(content="convo note", requested_by_user=False)

        convo_path = (
            tmp_path / "entries" / "_global" / "convo" / entry.date / f"{entry.slug}.md"
        )
        assert convo_path.exists()

    def test_convo_frontmatter_includes_project(self, tmp_path: Path) -> None:
        """Convo frontmatter includes project field."""
        storage = Storage(tmp_path)

        entry = storage.save_convo_record(
            content="proj convo",
            requested_by_user=True,
            project="myproj",
        )

        assert entry.metadata.get("project") == "myproj"


# =============================================================================
# save_collab_record with project
# =============================================================================


class TestSaveCollabRecordWithProject:
    def test_saves_under_project_collab_directory(self, tmp_path: Path) -> None:
        """save_collab_record with project saves to entries/{project}/collab/{date}/."""
        storage = Storage(tmp_path)

        path = storage.save_collab_record(_collab_record(), project="myproj")

        assert "entries/myproj/collab/2026-03-05" in str(path)
        assert path.exists()

    def test_collab_defaults_to_global(self, tmp_path: Path) -> None:
        """save_collab_record without project saves to entries/_global/collab/{date}/."""
        storage = Storage(tmp_path)

        path = storage.save_collab_record(_collab_record())

        assert "entries/_global/collab/2026-03-05" in str(path)
        assert path.exists()

    def test_collab_frontmatter_includes_project(self, tmp_path: Path) -> None:
        """Collab record frontmatter must include a 'project' key."""
        storage = Storage(tmp_path)

        path = storage.save_collab_record(_collab_record(), project="myproj")

        raw = path.read_text()
        assert raw.startswith("---\n")
        parts = raw.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["project"] == "myproj"

    def test_collab_frontmatter_project_defaults_to_global(self, tmp_path: Path) -> None:
        """Collab record frontmatter project defaults to '_global' when project is None."""
        storage = Storage(tmp_path)

        path = storage.save_collab_record(_collab_record(), project=None)

        raw = path.read_text()
        parts = raw.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["project"] == "_global"


# =============================================================================
# list_indexable_documents with project
# =============================================================================


class TestListIndexableDocumentsWithProject:
    def test_returns_only_specified_project_docs(self, tmp_path: Path) -> None:
        """list_indexable_documents(project='myproj') returns only that project's docs."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="a", content="# A", metadata={"topic": "x"}),
            project="myproj",
        )
        storage.save_entry(
            Entry(date="2026-03-06", slug="b", content="# B", metadata={"topic": "y"}),
            project="other",
        )

        docs = storage.list_indexable_documents(project="myproj")

        doc_ids = [d["doc_id"] for d in docs]
        assert any("myproj" in did for did in doc_ids)
        assert not any("other" in did for did in doc_ids)

    def test_returns_all_when_project_none(self, tmp_path: Path) -> None:
        """list_indexable_documents(project=None) returns docs from all projects."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="a", content="# A", metadata={"topic": "x"}),
            project="proj1",
        )
        storage.save_entry(
            Entry(date="2026-03-06", slug="b", content="# B", metadata={"topic": "y"}),
            project="proj2",
        )

        docs = storage.list_indexable_documents(project=None)

        doc_ids = [d["doc_id"] for d in docs]
        assert any("proj1" in did for did in doc_ids)
        assert any("proj2" in did for did in doc_ids)

    def test_includes_project_key_in_returned_dicts(self, tmp_path: Path) -> None:
        """Returned dicts include a 'project' key."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="a", content="# A", metadata={"topic": "x"}),
            project="myproj",
        )

        docs = storage.list_indexable_documents(project="myproj")

        assert len(docs) >= 1
        assert docs[0]["project"] == "myproj"

    def test_includes_convo_and_collab_for_project(self, tmp_path: Path) -> None:
        """list_indexable_documents includes convo and collab docs for the project."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="e", content="# E", metadata={"topic": "x"}),
            project="myproj",
        )
        storage.save_convo_record(content="convo text", requested_by_user=True, project="myproj")
        storage.save_collab_record(_collab_record(), project="myproj")

        docs = storage.list_indexable_documents(project="myproj")

        record_types = {d["record_type"] for d in docs}
        assert "entry" in record_types
        assert "convo" in record_types
        assert "collab" in record_types

    def test_global_project_indexable_docs(self, tmp_path: Path) -> None:
        """list_indexable_documents returns _global docs when no project filter."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="g", content="# G", metadata={"topic": "x"}),
            project=None,
        )

        docs = storage.list_indexable_documents(project=None)

        assert len(docs) >= 1
        assert any("_global" in d["doc_id"] for d in docs)


# =============================================================================
# read_entry with project
# =============================================================================


class TestReadEntryWithProject:
    def test_read_entry_from_project(self, tmp_path: Path) -> None:
        """read_entry with project reads from the project directory."""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06", slug="read-proj", content="# Read", metadata={"topic": "x"}
        )
        storage.save_entry(entry, project="myproj")

        loaded = storage.read_entry("2026-03-06", "read-proj", project="myproj")

        assert loaded is not None
        assert "# Read" in loaded.content

    def test_read_entry_from_global(self, tmp_path: Path) -> None:
        """read_entry without project reads from _global."""
        storage = Storage(tmp_path)
        entry = Entry(
            date="2026-03-06", slug="read-global", content="# Global", metadata={"topic": "x"}
        )
        storage.save_entry(entry, project=None)

        loaded = storage.read_entry("2026-03-06", "read-global", project=None)

        assert loaded is not None
        assert "# Global" in loaded.content

    def test_read_entry_isolation(self, tmp_path: Path) -> None:
        """read_entry for project A should not find project B's entries."""
        storage = Storage(tmp_path)
        storage.save_entry(
            Entry(date="2026-03-06", slug="iso", content="# Iso", metadata={"topic": "x"}),
            project="projA",
        )

        loaded = storage.read_entry("2026-03-06", "iso", project="projB")

        assert loaded is None


# =============================================================================
# _resolve_project validation
# =============================================================================


class TestResolveProjectValidation:
    """Project names must pass regex and must not collide with reserved names."""

    def test_reserved_name_global_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="reserved project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="global",
            )

    def test_reserved_name_convo_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="reserved project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="convo",
            )

    def test_reserved_name_collab_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="reserved project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="collab",
            )

    def test_path_traversal_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="Invalid project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="../escape",
            )

    def test_nested_path_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="Invalid project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="a/b",
            )

    def test_whitespace_only_raises(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        with pytest.raises(ValueError, match="Invalid project name"):
            storage.save_entry(
                Entry(date="2026-03-06", slug="x", content="c", metadata={"topic": "t"}),
                project="  ",
            )

    def test_empty_string_defaults_to_global(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        path = storage.save_entry(
            Entry(date="2026-03-06", slug="empty", content="c", metadata={"topic": "t"}),
            project="",
        )
        assert "_global" in str(path)

    def test_valid_name_with_dots_and_hyphens_accepted(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        path = storage.save_entry(
            Entry(date="2026-03-06", slug="ok", content="c", metadata={"topic": "t"}),
            project="valid-name.v2",
        )
        assert "valid-name.v2" in str(path)

    def test_underscore_global_accepted(self, tmp_path: Path) -> None:
        """'_global' is the default project and must be accepted (not reserved)."""
        storage = Storage(tmp_path)
        path = storage.save_entry(
            Entry(date="2026-03-06", slug="ok", content="c", metadata={"topic": "t"}),
            project="_global",
        )
        assert "_global" in str(path)


# =============================================================================
# list_convo_entries with project filtering
# =============================================================================


class TestListConvoEntriesWithProjectFiltering:
    """list_convo_entries(project=...) returns only matching project's convo records."""

    def test_returns_only_specified_project_convos(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        storage.save_convo_record(content="proj-a convo", requested_by_user=True, project="projA")
        storage.save_convo_record(content="proj-b convo", requested_by_user=True, project="projB")

        entries = storage.list_convo_entries(project="projA")

        assert len(entries) == 1
        assert "proj-a convo" in entries[0].content

    def test_returns_all_when_project_is_none(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        storage.save_convo_record(content="convo 1", requested_by_user=True, project="projA")
        storage.save_convo_record(content="convo 2", requested_by_user=True, project="projB")
        storage.save_convo_record(content="convo 3", requested_by_user=True, project=None)

        entries = storage.list_convo_entries(project=None)

        assert len(entries) == 3

    def test_returns_empty_for_nonexistent_project(self, tmp_path: Path) -> None:
        storage = Storage(tmp_path)
        storage.save_convo_record(content="exists", requested_by_user=True, project="projA")

        entries = storage.list_convo_entries(project="nope")

        assert entries == []
