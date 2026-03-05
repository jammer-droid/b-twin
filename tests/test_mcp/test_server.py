"""Test MCP server tools — data-only architecture."""

from unittest.mock import patch, MagicMock

from btwin.mcp.server import (
    mcp,
    btwin_start_session,
    btwin_end_session,
    btwin_search,
    btwin_record,
    btwin_convo_record,
    btwin_session_status,
    btwin_import_entry,
    read_entry,
)


def test_server_name():
    assert mcp.name == "btwin"


def _mock_twin():
    mock = MagicMock()
    mock.start_session.return_value = {"active": True, "topic": "test", "created_at": "2026-03-02T00:00:00"}
    mock.search.return_value = [
        {"id": "doc-1", "content": "Past record", "metadata": {"date": "2026-03-02", "slug": "test"}, "distance": 0.1}
    ]
    mock.record.return_value = {"date": "2026-03-02", "slug": "note-120000", "path": "/tmp/note.md"}
    mock.record_convo.return_value = {
        "date": "2026-03-02",
        "slug": "convo-120000",
        "path": "/tmp/.btwin/entries/convo/2026-03-02/convo-120000.md",
    }
    mock.end_session.return_value = {"date": "2026-03-02", "slug": "greeting", "summary": "- Greeted user"}
    mock.session_status.return_value = {"active": True, "topic": "test", "message_count": 2, "created_at": "2026-03-02T00:00:00"}
    return mock


# --- btwin_start_session ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_start_session(mock_get_twin):
    mock_get_twin.return_value = _mock_twin()
    result = btwin_start_session(topic="shader-study")
    assert "Session started" in result
    assert "test" in result


@patch("btwin.mcp.server._get_twin")
def test_btwin_start_session_no_topic(mock_get_twin):
    mock = _mock_twin()
    mock.start_session.return_value = {"active": True, "topic": None, "created_at": "2026-03-02T00:00:00"}
    mock_get_twin.return_value = mock
    result = btwin_start_session()
    assert "untitled" in result


# --- btwin_end_session ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_end_session(mock_get_twin):
    mock_get_twin.return_value = _mock_twin()
    result = btwin_end_session(summary="User greeted", slug="greeting")
    assert "Session saved" in result
    assert "Greeted user" in result


@patch("btwin.mcp.server._get_twin")
def test_btwin_end_session_no_active(mock_get_twin):
    mock = _mock_twin()
    mock.end_session.return_value = None
    mock_get_twin.return_value = mock
    result = btwin_end_session(summary="test")
    assert result == "No active session to end."


# --- btwin_search ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_search(mock_get_twin):
    mock_get_twin.return_value = _mock_twin()
    result = btwin_search("Unreal")
    assert "test" in result
    assert "Past record" in result


@patch("btwin.mcp.server._get_twin")
def test_btwin_search_with_record_type_filter(mock_get_twin):
    mock = _mock_twin()
    mock_get_twin.return_value = mock

    btwin_search("Unreal", record_type="convo")

    mock.search.assert_called_once_with("Unreal", n_results=5, filters={"record_type": "convo"})


@patch("btwin.mcp.server._get_twin")
def test_btwin_search_empty(mock_get_twin):
    mock = _mock_twin()
    mock.search.return_value = []
    mock_get_twin.return_value = mock
    result = btwin_search("nothing")
    assert result == "No matching records found."


# --- btwin_record ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_record(mock_get_twin):
    mock_get_twin.return_value = _mock_twin()
    result = btwin_record("Test note", topic="test")
    assert "Recorded" in result


@patch("btwin.mcp.server._get_audit_logger")
@patch("btwin.mcp.server._get_twin")
def test_btwin_convo_record(mock_get_twin, mock_get_audit_logger):
    mock = _mock_twin()
    mock_get_twin.return_value = mock
    audit_mock = MagicMock()
    mock_get_audit_logger.return_value = audit_mock

    result = btwin_convo_record("기억해줘", requested_by_user=True)

    mock.record_convo.assert_called_once_with("기억해줘", requested_by_user=True)
    audit_mock.log.assert_called_once()
    assert "entries/convo" in result


# --- btwin_session_status ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_session_status(mock_get_twin):
    mock_get_twin.return_value = _mock_twin()
    result = btwin_session_status()
    assert "Active session: test" in result
    assert "Messages: 2" in result


@patch("btwin.mcp.server._get_twin")
def test_btwin_session_status_no_session(mock_get_twin):
    mock = _mock_twin()
    mock.session_status.return_value = {"active": False}
    mock_get_twin.return_value = mock
    result = btwin_session_status()
    assert result == "No active session."


# --- read_entry ---

@patch("btwin.mcp.server._get_twin")
def test_read_entry_found(mock_get_twin):
    mock = _mock_twin()
    mock.storage.read_entry.return_value = MagicMock(
        date="2026-03-02", slug="test-entry", content="# Test Entry\n\nSome content"
    )
    mock_get_twin.return_value = mock
    result = read_entry("2026-03-02", "test-entry")
    assert "Test Entry" in result
    assert "Some content" in result


@patch("btwin.mcp.server._get_twin")
def test_read_entry_not_found(mock_get_twin):
    mock = _mock_twin()
    mock.storage.read_entry.return_value = None
    mock_get_twin.return_value = mock
    result = read_entry("2026-03-02", "nonexistent")
    assert "not found" in result.lower()


# --- btwin_import_entry ---

@patch("btwin.mcp.server._get_twin")
def test_btwin_import_entry(mock_get_twin):
    mock = _mock_twin()
    mock.import_entry.return_value = {
        "date": "2026-02-24",
        "slug": "ea-report",
        "path": "/tmp/entries/2026-02-24/ea-report.md",
    }
    mock_get_twin.return_value = mock
    result = btwin_import_entry(
        content="# EA Report\n\nAnalysis.",
        date="2026-02-24",
        slug="ea-report",
        tags="jobs,ea-korea",
        source_path="/fake/report.md",
    )
    mock.import_entry.assert_called_once_with(
        content="# EA Report\n\nAnalysis.",
        date="2026-02-24",
        slug="ea-report",
        tags=["jobs", "ea-korea"],
        source_path="/fake/report.md",
    )
    assert "2026-02-24" in result
    assert "ea-report" in result


@patch("btwin.mcp.server._get_twin")
def test_btwin_import_entry_no_tags(mock_get_twin):
    mock = _mock_twin()
    mock.import_entry.return_value = {
        "date": "2026-02-24",
        "slug": "note",
        "path": "/tmp/entries/2026-02-24/note.md",
    }
    mock_get_twin.return_value = mock
    result = btwin_import_entry(
        content="Just a note.",
        date="2026-02-24",
        slug="note",
    )
    mock.import_entry.assert_called_once_with(
        content="Just a note.",
        date="2026-02-24",
        slug="note",
        tags=None,
        source_path=None,
    )
    assert "Imported" in result
