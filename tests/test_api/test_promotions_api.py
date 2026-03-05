from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def _collab_payload(**overrides):
    base = {
        "taskId": "jeonse-e2e-001",
        "recordType": "collab",
        "summary": "E2E 서버 충돌 원인 파악 및 수정",
        "evidence": ["tsx integration 11/11 pass"],
        "nextAction": ["CI 스크립트 정리"],
        "status": "completed",
        "authorAgent": "codex-code",
        "createdAt": "2026-03-05T15:54:00+09:00",
    }
    base.update(overrides)
    return base


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
        admin_token="secret-token",
    )
    return TestClient(app)


def _create_collab_record(client: TestClient) -> str:
    created = client.post("/api/collab/records", json=_collab_payload())
    assert created.status_code == 201
    return created.json()["recordId"]


def test_propose_promotion_and_list(tmp_path: Path):
    client = _client(tmp_path)
    record_id = _create_collab_record(client)

    proposed = client.post(
        "/api/promotions/propose",
        json={
            "sourceRecordId": record_id,
            "proposedBy": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )

    assert proposed.status_code == 201
    assert proposed.json()["status"] == "proposed"

    listed = client.get("/api/promotions?status=proposed")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_propose_requires_existing_source_record(tmp_path: Path):
    client = _client(tmp_path)

    proposed = client.post(
        "/api/promotions/propose",
        json={
            "sourceRecordId": "rec_missing",
            "proposedBy": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )

    assert proposed.status_code == 404
    assert proposed.json()["errorCode"] == "RECORD_NOT_FOUND"


def test_propose_rejects_actor_mismatch(tmp_path: Path):
    client = _client(tmp_path)
    record_id = _create_collab_record(client)

    proposed = client.post(
        "/api/promotions/propose",
        json={
            "sourceRecordId": record_id,
            "proposedBy": "codex-code",
        },
        headers={"X-Actor-Agent": "research-bot"},
    )

    assert proposed.status_code == 403
    assert proposed.json()["errorCode"] == "FORBIDDEN"


def test_approve_promotion_only_main_allowed(tmp_path: Path):
    client = _client(tmp_path)
    record_id = _create_collab_record(client)

    proposed = client.post(
        "/api/promotions/propose",
        json={
            "sourceRecordId": record_id,
            "proposedBy": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )
    item_id = proposed.json()["itemId"]

    denied = client.post(
        f"/api/promotions/{item_id}/approve",
        json={"actorAgent": "research-bot"},
        headers={"X-Actor-Agent": "research-bot"},
    )
    assert denied.status_code == 403
    assert denied.json()["errorCode"] == "FORBIDDEN"

    approved = client.post(
        f"/api/promotions/{item_id}/approve",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approvedBy"] == "main"


def test_approve_returns_not_found_for_missing_item(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post(
        "/api/promotions/prm_missing/approve",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )

    assert res.status_code == 404
    assert res.json()["errorCode"] == "PROMOTION_NOT_FOUND"


def test_run_batch_requires_main_and_admin_token(tmp_path: Path):
    client = _client(tmp_path)

    denied = client.post(
        "/api/promotions/run-batch",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )
    assert denied.status_code == 403
    assert denied.json()["errorCode"] == "FORBIDDEN"

    denied_non_main = client.post(
        "/api/promotions/run-batch",
        json={"actorAgent": "codex-code"},
        headers={"X-Actor-Agent": "codex-code", "X-Admin-Token": "secret-token"},
    )
    assert denied_non_main.status_code == 403
    assert denied_non_main.json()["errorCode"] == "FORBIDDEN"


def test_run_batch_promotes_approved_items_and_history(tmp_path: Path):
    client = _client(tmp_path)
    record_id = _create_collab_record(client)

    proposed = client.post(
        "/api/promotions/propose",
        json={
            "sourceRecordId": record_id,
            "proposedBy": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )
    assert proposed.status_code == 201
    item_id = proposed.json()["itemId"]

    approved = client.post(
        f"/api/promotions/{item_id}/approve",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )
    assert approved.status_code == 200

    batch = client.post(
        "/api/promotions/run-batch",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main", "X-Admin-Token": "secret-token"},
    )
    assert batch.status_code == 200
    assert batch.json()["promoted"] == 1

    denied_history = client.get("/api/promotions/history")
    assert denied_history.status_code == 403

    history = client.get("/api/promotions/history", headers={"X-Admin-Token": "secret-token"})
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["itemId"] == item_id
    assert items[0]["sourceRecordId"] == record_id
    assert items[0]["scope"] == "global"
