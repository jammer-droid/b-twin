"""Tests for project parameter wiring through BTwin core methods."""

from unittest.mock import patch, MagicMock
from pathlib import Path

from btwin.core.btwin import BTwin
from btwin.config import BTwinConfig


def make_btwin(tmp_path):
    """Create BTwin instance for testing (no LLM)."""
    config = BTwinConfig(data_dir=tmp_path)
    twin = BTwin(config)
    return twin


# ---------------------------------------------------------------------------
# record with project
# ---------------------------------------------------------------------------


def test_record_with_project(tmp_path):
    """BTwin.record(content, project='myproj') saves under the project directory."""
    twin = make_btwin(tmp_path)

    result = twin.record("Project note", topic="test", project="myproj")

    # Saved path should contain the project name
    assert "myproj" in result["path"]
    # Verify the file is stored in the project directory
    saved_path = Path(result["path"])
    assert saved_path.exists()
    assert "entries/myproj/" in result["path"]


def test_record_default_project(tmp_path):
    """BTwin.record(content) without project saves under _global."""
    twin = make_btwin(tmp_path)

    result = twin.record("Global note", topic="test")

    # Saved path should contain _global
    assert "_global" in result["path"]
    saved_path = Path(result["path"])
    assert saved_path.exists()
    assert "entries/_global/" in result["path"]


# ---------------------------------------------------------------------------
# record_convo with project
# ---------------------------------------------------------------------------


def test_record_convo_with_project(tmp_path):
    """BTwin.record_convo(content, project='myproj') saves under the project convo directory."""
    twin = make_btwin(tmp_path)

    result = twin.record_convo("Remember this", requested_by_user=True, project="myproj")

    assert "myproj" in result["path"]
    assert "convo" in result["path"]
    saved_path = Path(result["path"])
    assert saved_path.exists()


def test_record_convo_default_project(tmp_path):
    """BTwin.record_convo(content) without project saves under _global/convo."""
    twin = make_btwin(tmp_path)

    result = twin.record_convo("Remember this", requested_by_user=True)

    assert "_global" in result["path"]
    assert "convo" in result["path"]
    saved_path = Path(result["path"])
    assert saved_path.exists()


# ---------------------------------------------------------------------------
# import_entry with project
# ---------------------------------------------------------------------------


def test_import_entry_with_project(tmp_path):
    """BTwin.import_entry(..., project='myproj') saves under the project directory."""
    twin = make_btwin(tmp_path)

    result = twin.import_entry(
        content="# Report\n\nAnalysis.",
        date="2026-03-06",
        slug="report",
        tags=["test"],
        project="myproj",
    )

    assert "myproj" in result["path"]
    assert result["date"] == "2026-03-06"
    assert result["slug"] == "report"
    saved_path = Path(result["path"])
    assert saved_path.exists()
    assert "entries/myproj/" in result["path"]


def test_import_entry_default_project(tmp_path):
    """BTwin.import_entry(...) without project saves under _global."""
    twin = make_btwin(tmp_path)

    result = twin.import_entry(
        content="# Note\n\nContent.",
        date="2026-03-06",
        slug="note",
    )

    assert "_global" in result["path"]
    assert "entries/_global/" in result["path"]


# ---------------------------------------------------------------------------
# search with project
# ---------------------------------------------------------------------------


def test_search_with_project(tmp_path):
    """BTwin.search(query, project='myproj') passes project filter to vector store."""
    twin = make_btwin(tmp_path)

    with patch.object(twin.vector_store, "search", return_value=[]) as mock_search:
        twin.search("query", project="myproj")

    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args
    metadata_filters = call_kwargs.kwargs.get("metadata_filters") or call_kwargs[1].get("metadata_filters")
    assert metadata_filters is not None
    assert metadata_filters["project"] == "myproj"


def test_search_without_project(tmp_path):
    """BTwin.search(query) without project does not add project filter."""
    twin = make_btwin(tmp_path)

    with patch.object(twin.vector_store, "search", return_value=[]) as mock_search:
        twin.search("query")

    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args
    metadata_filters = call_kwargs.kwargs.get("metadata_filters") or call_kwargs[1].get("metadata_filters")
    # metadata_filters should be None (no project filter added)
    assert metadata_filters is None


def test_search_with_project_merges_existing_filters(tmp_path):
    """BTwin.search(query, filters={...}, project='myproj') merges project into existing filters."""
    twin = make_btwin(tmp_path)

    with patch.object(twin.vector_store, "search", return_value=[]) as mock_search:
        twin.search("query", filters={"record_type": "entry"}, project="myproj")

    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args
    metadata_filters = call_kwargs.kwargs.get("metadata_filters") or call_kwargs[1].get("metadata_filters")
    assert metadata_filters is not None
    assert metadata_filters["project"] == "myproj"
    assert metadata_filters["record_type"] == "entry"


# ---------------------------------------------------------------------------
# end_session with project
# ---------------------------------------------------------------------------


def test_end_session_with_project(tmp_path):
    """BTwin.end_session(project='myproj') saves session entry under the project directory."""
    twin = make_btwin(tmp_path)
    twin.start_session(topic="test-topic")
    twin.session_manager.add_message("user", "Hello")

    result = twin.end_session(summary="User said hello", slug="hello-test", project="myproj")

    assert result is not None
    assert result["slug"] == "hello-test"
    # Verify the entry was saved under the project path
    entries = twin.storage.list_entries(project="myproj")
    assert len(entries) == 1


def test_end_session_default_project(tmp_path):
    """BTwin.end_session() without project saves under _global."""
    twin = make_btwin(tmp_path)
    twin.start_session(topic="test-topic")
    twin.session_manager.add_message("user", "Hello")

    result = twin.end_session(summary="User said hello", slug="hello-test")

    assert result is not None
    # Default project is _global
    entries = twin.storage.list_entries(project="_global")
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# _index_file passes project
# ---------------------------------------------------------------------------


def test_index_file_passes_project(tmp_path):
    """_index_file passes project to mark_pending."""
    twin = make_btwin(tmp_path)

    # Create an entry file manually to have a path to index
    from btwin.core.models import Entry

    entry = Entry(
        date="2026-03-06",
        slug="idx-test",
        content="# Index Test",
        metadata={"topic": "test"},
    )
    saved_path = twin.storage.save_entry(entry, project="myproj")

    with patch.object(twin.indexer, "mark_pending") as mock_mark, \
         patch.object(twin.indexer, "repair", return_value={"ok": True}):
        twin._index_file(saved_path, record_type="entry", project="myproj")

    mock_mark.assert_called_once()
    call_kwargs = mock_mark.call_args
    assert call_kwargs.kwargs.get("project") == "myproj"


def test_index_file_without_project(tmp_path):
    """_index_file without project passes project=None to mark_pending."""
    twin = make_btwin(tmp_path)

    from btwin.core.models import Entry

    entry = Entry(
        date="2026-03-06",
        slug="idx-default",
        content="# Index Default",
        metadata={"topic": "test"},
    )
    saved_path = twin.storage.save_entry(entry, project=None)

    with patch.object(twin.indexer, "mark_pending") as mock_mark, \
         patch.object(twin.indexer, "repair", return_value={"ok": True}):
        twin._index_file(saved_path, record_type="entry")

    mock_mark.assert_called_once()
    call_kwargs = mock_mark.call_args
    # project should default to None
    assert call_kwargs.kwargs.get("project") is None
