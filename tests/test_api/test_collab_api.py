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


def test_handoff_integrity_gate_retries_repair_and_fails_safe(tmp_path: Path, monkeypatch):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(authorAgent="research-bot")).json()

    calls = {"count": 0}

    def always_unhealthy(self, doc_id: str):
        return {
            "ok": False,
            "doc_id": doc_id,
            "reason": "status_not_indexed",
            "status": "failed",
            "checksum_match": False,
            "vector_present": False,
        }

    def fail_repair(self, doc_id: str):
        calls["count"] += 1
        return {"ok": False, "doc_id": doc_id, "status": "failed", "error": "boom"}

    monkeypatch.setattr("btwin.api.collab_api.CoreIndexer.verify_doc_integrity", always_unhealthy)
    monkeypatch.setattr("btwin.api.collab_api.CoreIndexer.repair", fail_repair)

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

    assert res.status_code == 409
    assert res.json()["errorCode"] == "INTEGRITY_GATE_FAILED"
    assert calls["count"] == 2


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


def test_complete_idempotent_path_runs_integrity_repair_when_unhealthy(tmp_path: Path, monkeypatch):
    client = _client(tmp_path)
    created = client.post("/api/collab/records", json=_payload(status="completed")).json()

    state = {"calls": 0}

    def flaky_integrity(self, doc_id: str):
        state["calls"] += 1
        if state["calls"] == 1:
            return {
                "ok": False,
                "doc_id": doc_id,
                "reason": "vector_missing",
                "status": "indexed",
                "checksum_match": True,
                "vector_present": False,
            }
        return {
            "ok": True,
            "doc_id": doc_id,
            "reason": "healthy",
            "status": "indexed",
            "checksum_match": True,
            "vector_present": True,
        }

    monkeypatch.setattr("btwin.api.collab_api.CoreIndexer.verify_doc_integrity", flaky_integrity)

    repaired = {"count": 0}

    def ok_repair(self, doc_id: str):
        repaired["count"] += 1
        return {"ok": True, "doc_id": doc_id, "status": "indexed"}

    monkeypatch.setattr("btwin.api.collab_api.CoreIndexer.repair", ok_repair)

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
    assert repaired["count"] == 1


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


def test_admin_reload_requires_admin_token_and_actor_binding(tmp_path: Path):
    client = _client(tmp_path)

    denied_no_token = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main"},
    )
    assert denied_no_token.status_code == 403
    assert denied_no_token.json()["errorCode"] == "FORBIDDEN"

    denied_actor_mismatch = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "codex-code", "X-Admin-Token": "secret-token"},
    )
    assert denied_actor_mismatch.status_code == 403
    assert denied_actor_mismatch.json()["errorCode"] == "FORBIDDEN"

    allowed = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main"},
        headers={"X-Actor-Agent": "main", "X-Admin-Token": "secret-token"},
    )
    assert allowed.status_code == 200


def test_admin_reload_rejects_path_traversal(tmp_path: Path):
    """overridePath must resolve within the user's home directory."""
    client = _client(tmp_path)
    auth_headers = {"X-Actor-Agent": "main", "X-Admin-Token": "secret-token"}

    # Absolute path outside home directory
    res = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main", "overridePath": "/etc/passwd"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert res.json()["errorCode"] == "INVALID_PATH"

    # Path traversal via ..
    res = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main", "overridePath": "~/../../../etc/shadow"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert res.json()["errorCode"] == "INVALID_PATH"

    # Valid path within home directory should be accepted
    res = client.post(
        "/api/admin/agents/reload",
        json={"actorAgent": "main", "overridePath": "~/.btwin/agents.json"},
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_admin_endpoints_reject_bad_tokens(tmp_path: Path):
    """Admin-protected endpoints must reject None, empty, and wrong tokens."""
    client = _client(tmp_path)

    endpoints = [
        ("/api/admin/agents/reload", {"actorAgent": "main"}),
        ("/api/promotions/run-batch", {"actorAgent": "main"}),
    ]
    bad_token_cases = [
        ({}, "no token header"),
        ({"X-Admin-Token": ""}, "empty token"),
        ({"X-Admin-Token": "wrong-token"}, "wrong token"),
    ]

    for path, body in endpoints:
        for extra_headers, label in bad_token_cases:
            headers = {"X-Actor-Agent": "main", **extra_headers}
            res = client.post(path, json=body, headers=headers)
            assert res.status_code == 403, f"{path} should reject {label}"
            assert res.json()["errorCode"] == "FORBIDDEN"
