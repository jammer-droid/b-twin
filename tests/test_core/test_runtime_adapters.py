from datetime import UTC, datetime

from btwin.core.audit import AuditLogger
from btwin.core.runtime_adapters import OpenClawRecallAdapter, StandaloneRecallAdapter, build_runtime_adapters
from btwin.core.runtime_ports import AuditEvent, MemoryEntry, RecallQuery


class DummyOpenClawMemory:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    def memory_search(self, *, query: str, scope: str, limit: int) -> list[dict[str, object]]:
        _ = scope
        hits = [row for row in self.rows.values() if query.lower() in str(row.get("content", "")).lower()]
        return hits[:limit]

    def memory_get(self, *, record_id: str) -> dict[str, object] | None:
        return self.rows.get(record_id)

    def memory_remember(self, *, content: str, tags: list[str], source: str, timestamp: datetime) -> dict[str, object]:
        _ = tags, timestamp
        record_id = f"m-{len(self.rows) + 1}"
        row = {
            "record_id": record_id,
            "content": content,
            "source": source,
            "version": 3,
            "confidence": 0.9,
        }
        self.rows[record_id] = row
        return row


def test_attached_recall_adapter_bridges_openclaw_memory() -> None:
    memory = DummyOpenClawMemory()
    adapter = OpenClawRecallAdapter(memory=memory)

    ref = adapter.remember(MemoryEntry(content="hello attached", doc_version=2), source="api")
    assert ref.record_id == "m-1"

    rows = adapter.recall(RecallQuery(query="hello", limit=5))
    assert len(rows) == 1
    assert rows[0].source == "api"


def test_standalone_recall_adapter_works_without_openclaw(tmp_path) -> None:
    adapter = StandaloneRecallAdapter(journal_path=tmp_path / "memory_journal.jsonl")

    saved = adapter.remember(MemoryEntry(content="standalone memory", doc_version=5), tags=["local"], source="standalone")
    assert saved.record_id.startswith("mem_")

    results = adapter.recall(RecallQuery(query="standalone", limit=3))
    assert len(results) == 1
    assert results[0].version == 5


def test_attached_adapter_marks_degraded_when_openclaw_memory_unavailable(tmp_path) -> None:
    adapters = build_runtime_adapters(
        mode="attached",
        data_dir=tmp_path,
        audit_logger=AuditLogger(tmp_path / "audit.log.jsonl"),
        openclaw_memory=None,
    )

    assert isinstance(adapters.recall, StandaloneRecallAdapter)
    assert adapters.recall_backend == "standalone-journal"
    assert adapters.degraded is True
    assert adapters.degraded_reason is not None


def test_openclaw_recall_adapter_tolerates_malformed_numeric_fields() -> None:
    class MalformedMemory(DummyOpenClawMemory):
        def memory_search(self, *, query: str, scope: str, limit: int) -> list[dict[str, object]]:
            _ = query, scope, limit
            return [{"record_id": "bad-1", "content": "hello", "confidence": "bad", "version": "oops"}]

        def memory_remember(self, *, content: str, tags: list[str], source: str, timestamp: datetime) -> dict[str, object]:
            _ = content, tags, source, timestamp
            return {"id": "", "doc_version": "broken"}

    adapter = OpenClawRecallAdapter(memory=MalformedMemory())
    rows = adapter.recall(RecallQuery(query="hello", limit=3))

    assert len(rows) == 1
    assert rows[0].confidence == 0.0
    assert rows[0].version == 1

    remembered = adapter.remember(MemoryEntry(content="x", doc_version=7))
    assert remembered.doc_version == 7
    assert remembered.record_id.startswith("mem_")


def test_attached_audit_event_uses_runtime_envelope(tmp_path) -> None:
    adapters = build_runtime_adapters(
        mode="attached",
        data_dir=tmp_path,
        audit_logger=AuditLogger(tmp_path / "audit.log.jsonl"),
        openclaw_memory=DummyOpenClawMemory(),
    )

    adapters.audit.append(
        AuditEvent(
            event_type="indexer_refresh",
            actor="main",
            trace_id="trc_x",
            doc_version=7,
            checksum="sha256:abc",
            payload={"ok": True},
            timestamp=datetime.now(UTC),
        )
    )

    tail = adapters.audit.logger.tail(limit=1)
    envelope = tail[0]["payload"]
    assert envelope["mode"] == "attached"
    assert envelope["traceId"] == "trc_x"
    assert envelope["docVersion"] == 7

    # Issue 1: verify the outer event's traceId matches the caller's trace_id
    assert tail[0]["traceId"] == "trc_x"


def test_append_preserves_caller_trace_id_in_outer_event(tmp_path) -> None:
    """The outer audit log event's traceId must match the AuditEvent.trace_id
    passed by the caller, not be replaced by a newly generated uuid."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    logger = AuditLogger(tmp_path / "audit.log.jsonl")
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    adapter.append(
        AuditEvent(
            event_type="test_trace",
            actor="ci",
            trace_id="trc_myspecialid",
            doc_version=1,
            checksum="sha256:000",
            payload={},
            timestamp=datetime.now(UTC),
        )
    )

    raw = logger.tail(limit=1)[0]
    # The outer traceId must be the caller's, not a freshly generated one
    assert raw["traceId"] == "trc_myspecialid"
    # The envelope payload should also carry the same traceId
    assert raw["payload"]["traceId"] == "trc_myspecialid"


def test_query_respects_limit_parameter(tmp_path) -> None:
    """Issue 3: AuditPort.query() should accept and honour a limit parameter."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    logger = AuditLogger(tmp_path / "audit.log.jsonl")
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    # Write 20 events
    for i in range(20):
        adapter.append(
            AuditEvent(
                event_type="numbered",
                actor="bot",
                trace_id=f"trc_{i:04d}",
                doc_version=i,
                checksum="sha256:x",
                payload={"index": i},
                timestamp=datetime.now(UTC),
            )
        )

    # Default limit=500 should return all 20
    all_events = adapter.query()
    assert len(all_events) == 20

    # Explicit limit=5 should return only 5 (the last 5 logged)
    limited = adapter.query(limit=5)
    assert len(limited) == 5
    # They should be the last 5 events (indices 15..19)
    versions = [e.doc_version for e in limited]
    assert versions == [15, 16, 17, 18, 19]


# --- Issue I4: _coerce_int with Inf/NaN ---


def test_coerce_int_handles_positive_infinity() -> None:
    from btwin.core.runtime_adapters import _coerce_int

    assert _coerce_int(float("inf"), default=42) == 42


def test_coerce_int_handles_negative_infinity() -> None:
    from btwin.core.runtime_adapters import _coerce_int

    assert _coerce_int(float("-inf"), default=42) == 42


def test_coerce_int_handles_nan() -> None:
    from btwin.core.runtime_adapters import _coerce_int

    assert _coerce_int(float("nan"), default=42) == 42


def test_coerce_int_still_works_for_normal_values() -> None:
    from btwin.core.runtime_adapters import _coerce_int

    assert _coerce_int(7, default=0) == 7
    assert _coerce_int("13", default=0) == 13
    assert _coerce_int(3.9, default=0) == 3
    assert _coerce_int("not_a_number", default=-1) == -1
    assert _coerce_int(None, default=99) == 99


# --- Issue C1-P0: verify_integrity ---


def test_verify_integrity_valid_jsonl(tmp_path) -> None:
    """verify_integrity returns ok=True when all lines are valid."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    # Write valid audit events via the adapter
    for i in range(3):
        adapter.append(
            AuditEvent(
                event_type="test_event",
                actor="bot",
                trace_id=f"trc_{i:04d}",
                doc_version=i,
                checksum="sha256:x",
                payload={"i": i},
                timestamp=datetime.now(UTC),
            )
        )

    report = adapter.verify_integrity("")
    assert report.ok is True
    assert report.failed_ranges == []


def test_verify_integrity_malformed_json_lines(tmp_path) -> None:
    """verify_integrity returns ok=False with details when lines are not valid JSON."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    # Write a mix of valid and invalid lines
    log_path.write_text(
        '{"timestamp":"2026-01-01T00:00:00Z","eventType":"ok","traceId":"trc_1"}\n'
        "this is not json\n"
        '{"timestamp":"2026-01-02T00:00:00Z","eventType":"ok","traceId":"trc_2"}\n'
        "{truncated\n",
        encoding="utf-8",
    )

    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    report = adapter.verify_integrity("")
    assert report.ok is False
    assert len(report.failed_ranges) == 2
    assert "line 2" in report.failed_ranges[0]
    assert "invalid JSON" in report.failed_ranges[0]
    assert "line 4" in report.failed_ranges[1]
    assert "invalid JSON" in report.failed_ranges[1]


def test_verify_integrity_missing_required_fields(tmp_path) -> None:
    """verify_integrity reports lines with missing required fields."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    log_path.write_text(
        # Valid line
        '{"timestamp":"2026-01-01T00:00:00Z","eventType":"ok","traceId":"trc_1"}\n'
        # Missing eventType and traceId
        '{"timestamp":"2026-01-02T00:00:00Z"}\n'
        # Missing timestamp
        '{"eventType":"bad","traceId":"trc_3"}\n',
        encoding="utf-8",
    )

    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    report = adapter.verify_integrity("")
    assert report.ok is False
    assert len(report.failed_ranges) == 2
    # Line 2 should report missing eventType and traceId
    assert "line 2" in report.failed_ranges[0]
    assert "eventType" in report.failed_ranges[0]
    assert "traceId" in report.failed_ranges[0]
    # Line 3 should report missing timestamp
    assert "line 3" in report.failed_ranges[1]
    assert "timestamp" in report.failed_ranges[1]


def test_verify_integrity_range_name_filters_by_event_type(tmp_path) -> None:
    """When range_name is provided, only events matching that eventType are checked."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    log_path.write_text(
        # Valid event of type "alpha"
        '{"timestamp":"2026-01-01T00:00:00Z","eventType":"alpha","traceId":"trc_1"}\n'
        # Invalid event of type "beta" (missing traceId) -- should be checked
        '{"timestamp":"2026-01-02T00:00:00Z","eventType":"beta"}\n'
        # Invalid event of type "alpha" (missing timestamp) -- should be checked
        '{"eventType":"alpha","traceId":"trc_3"}\n',
        encoding="utf-8",
    )

    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    # Only check "alpha" events -- line 2 (beta) should be skipped
    report = adapter.verify_integrity("alpha")
    assert report.ok is False
    assert len(report.failed_ranges) == 1
    assert "line 3" in report.failed_ranges[0]
    assert "timestamp" in report.failed_ranges[0]

    # Only check "beta" events -- line 3 (alpha) should be skipped
    report_beta = adapter.verify_integrity("beta")
    assert report_beta.ok is False
    assert len(report_beta.failed_ranges) == 1
    assert "line 2" in report_beta.failed_ranges[0]
    assert "traceId" in report_beta.failed_ranges[0]


def test_verify_integrity_empty_file(tmp_path) -> None:
    """verify_integrity returns ok=True for an empty log file."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    log_path.write_text("", encoding="utf-8")

    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    report = adapter.verify_integrity("")
    assert report.ok is True
    assert report.failed_ranges == []


def test_verify_integrity_nonexistent_file(tmp_path) -> None:
    """verify_integrity returns ok=True when the log file doesn't exist yet."""
    from btwin.core.runtime_adapters import RuntimeAuditAdapter

    log_path = tmp_path / "audit.log.jsonl"
    log_path.unlink(missing_ok=True)

    logger = AuditLogger(log_path)
    adapter = RuntimeAuditAdapter(logger=logger, mode="standalone")

    report = adapter.verify_integrity("")
    assert report.ok is True
    assert report.failed_ranges == []
