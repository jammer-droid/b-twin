from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def _payload(**overrides):
    base = {
        "taskId": "jeonse-e2e-001",
        "recordType": "collab",
        "summary": "E2E 서버 충돌 원인 파악 및 수정",
        "evidence": ["tsx integration 11/11 pass"],
        "nextAction": ["CI 스크립트 정리"],
        "status": "draft",
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


def test_create_list_detail_collab_record(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post("/api/collab/records", json=_payload())
    assert res.status_code == 201
    record_id = res.json()["recordId"]

    listed = client.get("/api/collab/records").json()["items"]
    assert len(listed) == 1
    assert listed[0]["recordId"] == record_id

    detail = client.get(f"/api/collab/records/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["frontmatter"]["recordId"] == record_id


def test_create_record_supports_idempotency_key(tmp_path: Path):
    client = _client(tmp_path)

    headers = {"Idempotency-Key": "idem-1"}
    first = client.post("/api/collab/records", json=_payload(), headers=headers)
    second = client.post("/api/collab/records", json=_payload(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["idempotent"] is True


def test_create_record_rejects_idempotency_key_reuse_with_different_payload(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Idempotency-Key": "idem-dup"}

    first = client.post("/api/collab/records", json=_payload(summary="요약 A"), headers=headers)
    second = client.post("/api/collab/records", json=_payload(summary="요약 B"), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["errorCode"] == "DUPLICATE_RECORD"


def test_create_record_rejects_duplicate_tuple_with_different_payload(tmp_path: Path):
    client = _client(tmp_path)

    first = client.post("/api/collab/records", json=_payload(summary="요약 A"))
    assert first.status_code == 201

    second = client.post("/api/collab/records", json=_payload(summary="요약 B"))
    assert second.status_code == 409
    assert second.json()["errorCode"] == "DUPLICATE_RECORD"


def test_handoff_and_complete_gate_flow(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="research-bot")).json()

    handoff = client.post(
        "/api/collab/handoff",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "fromAgent": "research-bot",
            "toAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "research-bot"},
    )
    assert handoff.status_code == 200
    assert handoff.json()["status"] == "handed_off"
    assert handoff.json()["version"] == 2

    complete = client.post(
        "/api/collab/complete",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 2,
            "actorAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"
    assert complete.json()["version"] == 3


def test_complete_idempotent_retry_even_with_old_expected_version(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(status="completed")).json()

    retry = client.post(
        "/api/collab/complete",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "actorAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )

    assert retry.status_code == 200
    assert retry.json()["idempotent"] is True


def test_handoff_rejects_concurrent_modification(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="research-bot")).json()

    res = client.post(
        "/api/collab/handoff",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 99,
            "fromAgent": "research-bot",
            "toAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "research-bot"},
    )

    assert res.status_code == 409
    assert res.json()["errorCode"] == "CONCURRENT_MODIFICATION"


def test_handoff_rejects_invalid_transition(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(status="completed")).json()

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
    assert res.json()["errorCode"] == "INVALID_STATE_TRANSITION"


def test_handoff_rejects_unknown_actor(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="research-bot")).json()

    res = client.post(
        "/api/collab/handoff",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "fromAgent": "research-bot",
            "toAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "unknown-agent"},
    )

    assert res.status_code == 403
    assert res.json()["errorCode"] == "FORBIDDEN"


def test_handoff_rejects_when_from_agent_not_owner(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="codex-code")).json()

    res = client.post(
        "/api/collab/handoff",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "fromAgent": "research-bot",
            "toAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "research-bot"},
    )

    assert res.status_code == 403
    assert res.json()["errorCode"] == "FORBIDDEN"


def test_complete_rejects_actor_not_owner(tmp_path: Path):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="research-bot")).json()

    res = client.post(
        "/api/collab/complete",
        json={
            "recordId": created["recordId"],
            "expectedVersion": 1,
            "actorAgent": "codex-code",
        },
        headers={"X-Actor-Agent": "codex-code"},
    )

    assert res.status_code == 403
    assert res.json()["errorCode"] == "FORBIDDEN"


def test_validation_error_uses_standard_error_envelope(tmp_path: Path):
    client = _client(tmp_path)

    res = client.post("/api/collab/records", json={"taskId": "x"})

    assert res.status_code == 422
    body = res.json()
    assert body["errorCode"] == "INVALID_SCHEMA"
    assert "traceId" in body


def test_admin_reload_requires_main_or_admin_token(tmp_path: Path):
    client = _client(tmp_path)

    denied = client.post("/api/admin/agents/reload", json={"actorAgent": "codex-code"})
    assert denied.status_code == 403
    assert denied.json()["errorCode"] == "FORBIDDEN"

    allowed_main = client.post("/api/admin/agents/reload", json={"actorAgent": "main"})
    assert allowed_main.status_code == 200

    allowed_token = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "codex-code"},
        headers={"X-Admin-Token": "secret-token"},
    )
    assert allowed_token.status_code == 200
