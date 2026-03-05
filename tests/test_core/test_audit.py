from pathlib import Path

from btwin.core.audit import AuditLogger


def test_gate_rejection_is_logged_with_reason(tmp_path: Path):
    logger = AuditLogger(tmp_path / "audit.jsonl")

    event = logger.log(
        event_type="gate_rejected",
        payload={
            "endpoint": "/api/collab/handoff",
            "errorCode": "INVALID_STATE_TRANSITION",
            "reason": "cannot transition from completed to handed_off",
        },
    )

    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert event["eventType"] == "gate_rejected"
    assert event["payload"]["errorCode"] == "INVALID_STATE_TRANSITION"


def test_audit_tail_returns_latest_events(tmp_path: Path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.log(event_type="one", payload={"n": 1})
    logger.log(event_type="two", payload={"n": 2})

    tail = logger.tail(limit=1)

    assert len(tail) == 1
    assert tail[0]["eventType"] == "two"
