import json
from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
        admin_token="secret-token",
    )
    return TestClient(app)


def test_gate_rejection_writes_audit_event(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post(
        "/api/collab/records",
        json={
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "done",
            "evidence": ["ok"],
            "nextAction": ["none"],
            "status": "completed",
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
        },
    ).json()

    res = client.post(
        "/api/collab/handoff",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "fromAgent": "codex-code",
            "toAgent": "research-bot",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )
    assert res.status_code == 409

    audit_path = tmp_path / "audit.log.jsonl"
    lines = audit_path.read_text().strip().splitlines()
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last["eventType"] == "gate_rejected"


def test_promotion_actions_write_audit_events(tmp_path: Path):
    client = _client(tmp_path)

    created = client.post(
        "/api/collab/records",
        json={
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "done",
            "evidence": ["ok"],
            "nextAction": ["none"],
            "status": "completed",
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
        },
    ).json()

    proposed = client.post(
        "/api/promotions/propose",
        json={"sourceRecordId": created["recordId"], "proposedBy": "codex-code"},
        headers={"X-Actor-Agent": "codex-code"},
    ).json()

    client.post(
        f"/api/promotions/{proposed['itemId']}/approve",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )

    client.post(
        "/api/promotions/run-batch",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main", "X-Admin-Token": "secret-token"},
    )

    events = [json.loads(line)["eventType"] for line in (tmp_path / "audit.log.jsonl").read_text().splitlines()]
    assert "promotion_proposed" in events
    assert "promotion_approved" in events
    assert "promotion_batch_run" in events
