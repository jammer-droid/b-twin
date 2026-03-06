import json
from pathlib import Path
from unittest.mock import patch

from btwin.core.audit import AuditLogger, _tail_lines


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


# --- Issue 1: trace_id passthrough ---


def test_log_uses_caller_trace_id_when_provided(tmp_path: Path):
    logger = AuditLogger(tmp_path / "audit.jsonl")

    event = logger.log(
        event_type="test_event",
        payload={"key": "value"},
        trace_id="trc_caller12345",
    )

    assert event["traceId"] == "trc_caller12345"

    # Also verify it was persisted correctly
    persisted = json.loads((tmp_path / "audit.jsonl").read_text().strip())
    assert persisted["traceId"] == "trc_caller12345"


def test_log_autogenerates_trace_id_when_not_provided(tmp_path: Path):
    logger = AuditLogger(tmp_path / "audit.jsonl")

    event = logger.log(event_type="test_event", payload={})

    assert event["traceId"].startswith("trc_")
    assert len(event["traceId"]) == 16  # "trc_" + 12 hex chars


def test_log_autogenerates_trace_id_for_empty_string(tmp_path: Path):
    """An empty string trace_id should be treated as 'not provided'."""
    logger = AuditLogger(tmp_path / "audit.jsonl")

    event = logger.log(event_type="test_event", payload={}, trace_id="")

    assert event["traceId"].startswith("trc_")


# --- Issue 2: tail() reverse-read ---


def test_tail_does_not_read_entire_file(tmp_path: Path):
    """Verify that tail() uses _tail_lines (reverse-read) instead of
    reading the entire file into memory."""
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path)

    # Write 100 lines
    for i in range(100):
        logger.log(event_type=f"evt_{i}", payload={"i": i})

    # Patch Path.read_text to detect if it's called
    original_read_text = Path.read_text

    read_text_called = False

    def spy_read_text(self_path, *args, **kwargs):
        nonlocal read_text_called
        if self_path == log_path:
            read_text_called = True
        return original_read_text(self_path, *args, **kwargs)

    with patch.object(Path, "read_text", spy_read_text):
        result = logger.tail(limit=5)

    assert read_text_called is False, "tail() should not call read_text()"
    assert len(result) == 5
    # Verify they're the last 5 events
    assert result[0]["eventType"] == "evt_95"
    assert result[-1]["eventType"] == "evt_99"


def test_tail_lines_with_small_chunks(tmp_path: Path):
    """Force multiple chunk reads by using a tiny chunk size."""
    log_path = tmp_path / "audit.jsonl"
    lines = [json.dumps({"n": i}) for i in range(50)]
    log_path.write_text("\n".join(lines) + "\n")

    # Use a very small chunk size to force multiple iterations
    result = _tail_lines(log_path, 5, chunk_size=32)

    assert len(result) == 5
    assert [json.loads(r)["n"] for r in result] == [45, 46, 47, 48, 49]


def test_tail_when_limit_exceeds_file_lines(tmp_path: Path):
    """Requesting more lines than exist should return all lines."""
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.log(event_type="only_one", payload={})

    result = logger.tail(limit=100)

    assert len(result) == 1
    assert result[0]["eventType"] == "only_one"


def test_tail_empty_file(tmp_path: Path):
    log_path = tmp_path / "audit.jsonl"
    log_path.write_text("")

    logger = AuditLogger(log_path)
    result = logger.tail(limit=5)
    assert result == []


def test_tail_nonexistent_file(tmp_path: Path):
    logger = AuditLogger(tmp_path / "subdir" / "audit.jsonl")
    # File doesn't exist (only parent was created)
    (tmp_path / "subdir" / "audit.jsonl").unlink(missing_ok=True)
    result = logger.tail(limit=5)
    assert result == []
