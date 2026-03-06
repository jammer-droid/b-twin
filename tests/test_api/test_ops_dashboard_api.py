import json

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app
from btwin.core.indexer import CoreIndexer


def test_ops_dashboard_exposes_required_sections(tmp_path):
    app = create_collab_app(data_dir=tmp_path, runtime_mode="standalone", initial_agents={"main"})
    client = TestClient(app)

    idx = CoreIndexer(tmp_path)
    idx.repair("missing-doc")

    audit_row = {
        "timestamp": "2026-03-06T00:00:00+00:00",
        "traceId": "trc_manual",
        "eventType": "gate_rejected",
        "payload": {"recordId": "r1"},
    }
    (tmp_path / "audit.log.jsonl").write_text(json.dumps(audit_row) + "\n", encoding="utf-8")

    res = client.get("/api/ops/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert "indexerStatus" in body
    assert "failureQueue" in body
    assert "repairHistory" in body
    assert "gateViolations" in body
    assert body["runtime"]["mode"] == "standalone"
    assert body["runtime"]["recallAdapter"] == "standalone-journal"
    assert body["runtime"]["degraded"] is False
    assert body["runtime"]["degradedReason"] is None
    assert len(body["repairHistory"]) == 1
    assert len(body["gateViolations"]) == 1


def test_ops_dashboard_marks_attached_mode_degraded_without_openclaw_binding(tmp_path):
    app = create_collab_app(data_dir=tmp_path, runtime_mode="attached", initial_agents={"main"})
    client = TestClient(app)

    res = client.get("/api/ops/dashboard")
    assert res.status_code == 200
    body = res.json()

    assert body["runtime"]["mode"] == "attached"
    assert body["runtime"]["attached"] is True
    assert body["runtime"]["recallAdapter"] == "standalone-journal"
    assert body["runtime"]["degraded"] is True
    assert "openclaw memory binding" in body["runtime"]["degradedReason"]


def test_standalone_runtime_allows_core_flow_without_openclaw_config(tmp_path):
    app = create_collab_app(data_dir=tmp_path, runtime_mode="standalone")
    client = TestClient(app)

    res = client.post(
        "/api/collab/records",
        json={
            "taskId": "t-1",
            "recordType": "collab",
            "summary": "standalone create",
            "evidence": ["ok"],
            "nextAction": ["next"],
            "status": "draft",
            "authorAgent": "main",
            "createdAt": "2026-03-06T12:00:00+09:00",
        },
    )

    assert res.status_code == 201
    assert res.json()["status"] == "draft"


def test_ops_dashboard_ui_surface(tmp_path):
    app = create_collab_app(data_dir=tmp_path, runtime_mode="standalone", initial_agents={"main"})
    client = TestClient(app)

    res = client.get("/ops")
    assert res.status_code == 200
    assert "B-TWIN Ops Dashboard" in res.text
    assert "Admin token (optional)" in res.text
    assert "X-Admin-Token" in res.text
