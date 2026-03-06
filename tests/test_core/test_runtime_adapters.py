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
