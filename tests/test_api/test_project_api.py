"""Tests for project-aware API endpoints (Task 4).

Covers:
- POST /api/entries/record with/without projectId
- POST /api/entries/search with/without projectId & scope
- POST /api/entries/convo-record with projectId
- POST /api/entries/import with projectId
- POST /api/sessions/start, /api/sessions/end, GET /api/sessions/status
- GET /api/indexer/status?projectId=...
- POST /api/collab/records with projectId
"""

from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app
from btwin.core.storage import Storage


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
        admin_token=None,
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/entries/record
# ---------------------------------------------------------------------------


def test_record_entry_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/entries/record",
        json={"content": "Hello world", "topic": "greet", "projectId": "myproj"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "date" in body
    assert "slug" in body
    assert "path" in body
    # Verify the file actually lives under the project directory
    assert "myproj" in body["path"]


def test_record_entry_without_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/entries/record",
        json={"content": "Global note"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "date" in body
    assert "slug" in body
    assert "path" in body
    # _global is the default project directory
    assert "_global" in body["path"]


# ---------------------------------------------------------------------------
# POST /api/entries/search
# ---------------------------------------------------------------------------


def test_search_entries_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    # Seed two entries in different projects
    client.post(
        "/api/entries/record",
        json={"content": "alpha project note", "topic": "alpha", "projectId": "proj-a"},
    )
    client.post(
        "/api/entries/record",
        json={"content": "beta project note", "topic": "beta", "projectId": "proj-b"},
    )

    res = client.post(
        "/api/entries/search",
        json={"query": "project note", "nResults": 10, "projectId": "proj-a", "scope": "project"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "results" in body


def test_search_entries_scope_all(tmp_path: Path):
    client = _client(tmp_path)

    client.post(
        "/api/entries/record",
        json={"content": "note one", "topic": "t1", "projectId": "proj-a"},
    )

    res = client.post(
        "/api/entries/search",
        json={"query": "note", "scope": "all"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "results" in body


# ---------------------------------------------------------------------------
# POST /api/entries/convo-record
# ---------------------------------------------------------------------------


def test_convo_record_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/entries/convo-record",
        json={
            "content": "convo memory text",
            "requestedByUser": True,
            "topic": "onboarding",
            "projectId": "myproj",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "date" in body
    assert "slug" in body
    assert "path" in body
    assert "myproj" in body["path"]


# ---------------------------------------------------------------------------
# POST /api/entries/import
# ---------------------------------------------------------------------------


def test_import_entry_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/entries/import",
        json={
            "content": "imported content",
            "date": "2026-03-05",
            "slug": "imported-note",
            "tags": ["important"],
            "sourcePath": "/some/path.md",
            "projectId": "myproj",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["date"] == "2026-03-05"
    assert body["slug"] == "imported-note"
    assert "path" in body
    assert "myproj" in body["path"]


# ---------------------------------------------------------------------------
# POST /api/sessions/start + end + GET status
# ---------------------------------------------------------------------------


def test_session_start(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post("/api/sessions/start", json={"topic": "design review"})
    assert res.status_code == 200
    body = res.json()
    assert body["active"] is True
    assert body["topic"] == "design review"
    assert "created_at" in body


def test_session_end_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    # Start a session first
    client.post("/api/sessions/start", json={"topic": "test session"})

    res = client.post(
        "/api/sessions/end",
        json={
            "summary": "session ended summary",
            "slug": "test-session-slug",
            "projectId": "myproj",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "test-session-slug"
    assert body["summary"] == "session ended summary"
    assert "date" in body


def test_session_status(tmp_path: Path):
    client = _client(tmp_path)

    # Initially no active session
    res = client.get("/api/sessions/status")
    assert res.status_code == 200
    assert res.json()["active"] is False

    # Start a session
    client.post("/api/sessions/start", json={"topic": "status check"})

    res = client.get("/api/sessions/status")
    assert res.status_code == 200
    body = res.json()
    assert body["active"] is True
    assert body["topic"] == "status check"


# ---------------------------------------------------------------------------
# GET /api/indexer/status?projectId=...
# ---------------------------------------------------------------------------


def test_indexer_status_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    # Seed a record so there's something in the indexer
    client.post(
        "/api/entries/record",
        json={"content": "index me", "topic": "idx", "projectId": "myproj"},
    )

    res = client.get("/api/indexer/status?projectId=myproj")
    assert res.status_code == 200
    body = res.json()
    # status_summary returns dict[str, int]
    assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# POST /api/collab/records with projectId
# ---------------------------------------------------------------------------


def _collab_payload(**overrides):
    base = {
        "taskId": "proj-task-001",
        "recordType": "collab",
        "summary": "collab with project",
        "evidence": ["test pass"],
        "nextAction": ["deploy"],
        "status": "draft",
        "authorAgent": "codex-code",
        "createdAt": "2026-03-05T15:54:00+09:00",
    }
    base.update(overrides)
    return base


def test_create_collab_record_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post("/api/collab/records", json=_collab_payload(projectId="myproj"))
    assert res.status_code == 201
    body = res.json()
    assert "recordId" in body

    # Verify record is listable with project filter
    listed = client.get("/api/collab/records?projectId=myproj").json()["items"]
    assert len(listed) == 1
    assert listed[0]["recordId"] == body["recordId"]


def test_list_collab_records_with_project_id_filter(tmp_path: Path):
    client = _client(tmp_path)

    # Create records in different projects
    client.post("/api/collab/records", json=_collab_payload(projectId="proj-a"))
    client.post(
        "/api/collab/records",
        json=_collab_payload(taskId="proj-task-002", projectId="proj-b"),
    )

    all_records = client.get("/api/collab/records").json()["items"]
    assert len(all_records) == 2

    proj_a_records = client.get("/api/collab/records?projectId=proj-a").json()["items"]
    assert len(proj_a_records) == 1

    proj_b_records = client.get("/api/collab/records?projectId=proj-b").json()["items"]
    assert len(proj_b_records) == 1


# ---------------------------------------------------------------------------
# GET /api/ops/dashboard?projectId=...
# ---------------------------------------------------------------------------


def test_ops_dashboard_with_project_id(tmp_path: Path):
    client = _client(tmp_path)

    res = client.get("/api/ops/dashboard?projectId=myproj")
    assert res.status_code == 200
    body = res.json()
    assert "indexerStatus" in body


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_session_end_without_active_session(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/sessions/end",
        json={"summary": "no session", "slug": "orphan"},
    )
    assert res.status_code == 200
    # When no session is active, end_session returns None -> API returns null/empty
    body = res.json()
    assert body is None or body == {}


def test_record_entry_rejects_extra_fields(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/entries/record",
        json={"content": "hello", "extraField": "bad"},
    )
    assert res.status_code == 422
