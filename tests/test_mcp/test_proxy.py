"""Tests for B-TWIN MCP Proxy -- verifies HTTP forwarding and projectId injection."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

import httpx

from btwin.mcp import proxy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_proxy_state():
    """Reset module-level proxy state before each test."""
    proxy._project = "test-proj"
    proxy._backend = "http://localhost:8787"
    proxy._client = None
    yield
    proxy._client = None


_MISSING = object()


def _mock_response(json_data: dict | list | None = _MISSING, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not _MISSING else {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_client() -> MagicMock:
    """Create a mock httpx.Client and install it as the proxy's client."""
    mock_client = MagicMock(spec=httpx.Client)
    proxy._client = mock_client
    return mock_client


# ---------------------------------------------------------------------------
# btwin_record
# ---------------------------------------------------------------------------


class TestBtwinRecord:
    def test_sends_project_id(self):
        client = _make_client()
        client.post.return_value = _mock_response({"path": "entries/test-proj/2026-03-06/note.md"})

        result = proxy.btwin_record("hello world", topic="test")

        client.post.assert_called_once()
        path, = client.post.call_args.args
        body = client.post.call_args.kwargs["json"]
        assert path == "/api/entries/record"
        assert body["projectId"] == "test-proj"
        assert body["content"] == "hello world"
        assert body["topic"] == "test"
        assert "Recorded" in result

    def test_without_topic(self):
        client = _make_client()
        client.post.return_value = _mock_response({"path": "entries/test-proj/2026-03-06/note.md"})

        proxy.btwin_record("just a note")

        body = client.post.call_args.kwargs["json"]
        assert "topic" not in body
        assert body["content"] == "just a note"

    def test_no_project_configured(self):
        proxy._project = ""
        client = _make_client()
        client.post.return_value = _mock_response({"path": "entries/default/2026-03-06/note.md"})

        proxy.btwin_record("note without project")

        body = client.post.call_args.kwargs["json"]
        assert "projectId" not in body


# ---------------------------------------------------------------------------
# btwin_search
# ---------------------------------------------------------------------------


class TestBtwinSearch:
    def test_project_scope_injects_project_id(self):
        client = _make_client()
        client.post.return_value = _mock_response([
            {
                "content": "past record",
                "metadata": {"date": "2026-03-02", "slug": "test-slug"},
            }
        ])

        result = proxy.btwin_search("Unreal")

        body = client.post.call_args.kwargs["json"]
        assert body["projectId"] == "test-proj"
        assert body["query"] == "Unreal"
        assert body["nResults"] == 5
        assert body["scope"] == "project"
        assert "test-slug" in result

    def test_all_scope_does_not_inject_project_id(self):
        client = _make_client()
        client.post.return_value = _mock_response([
            {"content": "cross-project result", "metadata": {"date": "2026-03-01", "slug": "global"}},
        ])

        result = proxy.btwin_search("career", scope="all")

        body = client.post.call_args.kwargs["json"]
        assert "projectId" not in body
        assert body["scope"] == "all"
        assert "global" in result

    def test_empty_results(self):
        client = _make_client()
        client.post.return_value = _mock_response([])

        result = proxy.btwin_search("nothing")
        assert result == "No matching records found."

    def test_non_list_result(self):
        client = _make_client()
        client.post.return_value = _mock_response({"message": "some dict response"})

        result = proxy.btwin_search("query")
        assert "some dict response" in result

    def test_custom_n_results(self):
        client = _make_client()
        client.post.return_value = _mock_response([])

        proxy.btwin_search("test", n_results=10)

        body = client.post.call_args.kwargs["json"]
        assert body["nResults"] == 10


# ---------------------------------------------------------------------------
# btwin_convo_record
# ---------------------------------------------------------------------------


class TestBtwinConvoRecord:
    def test_sends_project_id_and_requested_by_user(self):
        client = _make_client()
        client.post.return_value = _mock_response(
            {"path": "entries/convo/test-proj/2026-03-06/convo.md"}
        )

        result = proxy.btwin_convo_record("remember this", requested_by_user=True)

        body = client.post.call_args.kwargs["json"]
        assert body["projectId"] == "test-proj"
        assert body["content"] == "remember this"
        assert body["requestedByUser"] is True
        assert "Convo recorded" in result

    def test_default_requested_by_user_false(self):
        client = _make_client()
        client.post.return_value = _mock_response({"path": "ok"})

        proxy.btwin_convo_record("auto record")

        body = client.post.call_args.kwargs["json"]
        assert body["requestedByUser"] is False


# ---------------------------------------------------------------------------
# btwin_import_entry
# ---------------------------------------------------------------------------


class TestBtwinImportEntry:
    def test_sends_project_id_and_converts_tags(self):
        client = _make_client()
        client.post.return_value = _mock_response({
            "date": "2026-02-24",
            "slug": "ea-report",
            "path": "entries/test-proj/2026-02-24/ea-report.md",
        })

        result = proxy.btwin_import_entry(
            content="# Report",
            date="2026-02-24",
            slug="ea-report",
            tags="jobs, ea-korea, interview",
            source_path="/original/report.md",
        )

        body = client.post.call_args.kwargs["json"]
        assert body["projectId"] == "test-proj"
        assert body["content"] == "# Report"
        assert body["date"] == "2026-02-24"
        assert body["slug"] == "ea-report"
        assert body["tags"] == ["jobs", "ea-korea", "interview"]
        assert body["sourcePath"] == "/original/report.md"
        assert "Imported" in result
        assert "2026-02-24" in result

    def test_without_tags_and_source_path(self):
        client = _make_client()
        client.post.return_value = _mock_response({
            "date": "2026-02-24",
            "slug": "note",
            "path": "ok",
        })

        proxy.btwin_import_entry(content="Just a note.", date="2026-02-24", slug="note")

        body = client.post.call_args.kwargs["json"]
        assert "tags" not in body
        assert "sourcePath" not in body
        assert body["projectId"] == "test-proj"


# ---------------------------------------------------------------------------
# btwin_start_session
# ---------------------------------------------------------------------------


class TestBtwinStartSession:
    def test_does_not_inject_project_id(self):
        """SessionStartRequest has extra='forbid' and no projectId field."""
        client = _make_client()
        client.post.return_value = _mock_response({"topic": "shader-study"})

        result = proxy.btwin_start_session(topic="shader-study")

        path, = client.post.call_args.args
        body = client.post.call_args.kwargs["json"]
        assert path == "/api/sessions/start"
        assert "projectId" not in body
        assert body.get("topic") == "shader-study"
        assert "Session started" in result

    def test_without_topic(self):
        client = _make_client()
        client.post.return_value = _mock_response({"topic": None})

        result = proxy.btwin_start_session()

        body = client.post.call_args.kwargs["json"]
        assert "topic" not in body
        assert "untitled" in result


# ---------------------------------------------------------------------------
# btwin_end_session
# ---------------------------------------------------------------------------


class TestBtwinEndSession:
    def test_sends_project_id(self):
        client = _make_client()
        client.post.return_value = _mock_response({
            "date": "2026-03-06",
            "slug": "shader-study",
        })

        result = proxy.btwin_end_session(summary="Studied shaders", slug="shader-study")

        body = client.post.call_args.kwargs["json"]
        assert body["projectId"] == "test-proj"
        assert body["summary"] == "Studied shaders"
        assert body["slug"] == "shader-study"
        assert "Session saved" in result

    def test_without_slug(self):
        client = _make_client()
        client.post.return_value = _mock_response({"date": "2026-03-06", "slug": "auto"})

        proxy.btwin_end_session(summary="test")

        body = client.post.call_args.kwargs["json"]
        assert "slug" not in body
        assert body["summary"] == "test"

    def test_no_active_session(self):
        client = _make_client()
        client.post.return_value = _mock_response(None)

        result = proxy.btwin_end_session(summary="test")
        assert result == "No active session to end."


# ---------------------------------------------------------------------------
# btwin_session_status
# ---------------------------------------------------------------------------


class TestBtwinSessionStatus:
    def test_active_session(self):
        client = _make_client()
        client.get.return_value = _mock_response({
            "active": True,
            "topic": "shader-study",
            "message_count": 5,
            "created_at": "2026-03-06T10:00:00",
        })

        result = proxy.btwin_session_status()

        client.get.assert_called_once()
        path, = client.get.call_args.args
        assert path == "/api/sessions/status"
        assert "Active session: shader-study" in result
        assert "Messages: 5" in result

    def test_no_active_session(self):
        client = _make_client()
        client.get.return_value = _mock_response({"active": False})

        result = proxy.btwin_session_status()
        assert result == "No active session."


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_backend_error_raises(self):
        client = _make_client()
        client.post.return_value = _mock_response(None, status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            proxy.btwin_record("should fail")

    def test_backend_404_raises(self):
        client = _make_client()
        client.get.return_value = _mock_response(None, status_code=404)

        with pytest.raises(httpx.HTTPStatusError):
            proxy.btwin_session_status()


# ---------------------------------------------------------------------------
# Lazy client initialisation
# ---------------------------------------------------------------------------


class TestHttpClientInit:
    def test_lazy_init_creates_client(self):
        """_http() should create a client on first call."""
        proxy._client = None
        proxy._backend = "http://localhost:9999"

        client = proxy._http()

        assert client is not None
        assert isinstance(client, httpx.Client)
        # Clean up
        client.close()

    def test_lazy_init_reuses_client(self):
        """_http() should return the same client on subsequent calls."""
        proxy._client = None
        proxy._backend = "http://localhost:9999"

        client1 = proxy._http()
        client2 = proxy._http()

        assert client1 is client2
        client1.close()


# ---------------------------------------------------------------------------
# MCP server name
# ---------------------------------------------------------------------------


def test_mcp_server_name():
    assert proxy.mcp.name == "btwin"
