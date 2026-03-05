from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app
from btwin.core.models import Entry
from btwin.core.storage import Storage


def _client(tmp_path: Path, admin_token: str | None = None) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
        admin_token=admin_token,
    )
    return TestClient(app)


def test_entries_api_filters_by_record_type(tmp_path: Path):
    storage = Storage(tmp_path)
    storage.save_entry(
        Entry(
            date="2026-03-05",
            slug="entry-1",
            content="general note",
            metadata={"recordType": "entry"},
        )
    )
    storage.save_convo_record(content="convo memo", requested_by_user=True)

    client = _client(tmp_path)
    created = client.post(
        "/api/collab/records",
        json={
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "E2E 서버 충돌 원인 파악 및 수정",
            "evidence": ["tsx integration 11/11 pass"],
            "nextAction": ["CI 스크립트 정리"],
            "status": "draft",
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
        },
    )
    assert created.status_code == 201

    all_items = client.get("/api/entries").json()["items"]
    types = {item["recordType"] for item in all_items}
    assert "entry" in types
    assert "convo" in types
    assert "collab" in types

    collab_items = client.get("/api/entries?recordType=collab").json()["items"]
    assert len(collab_items) == 1
    assert collab_items[0]["recordType"] == "collab"

    convo_items = client.get("/api/entries?recordType=convo").json()["items"]
    assert len(convo_items) == 1
    assert convo_items[0]["recordType"] == "convo"


def test_entries_api_requires_admin_token_when_configured(tmp_path: Path):
    storage = Storage(tmp_path)
    storage.save_convo_record(content="convo memo", requested_by_user=True)

    client = _client(tmp_path, admin_token="secret-token")

    denied = client.get("/api/entries")
    assert denied.status_code == 403
    assert denied.json()["errorCode"] == "FORBIDDEN"

    allowed = client.get("/api/entries", headers={"X-Admin-Token": "secret-token"})
    assert allowed.status_code == 200
    assert len(allowed.json()["items"]) >= 1
