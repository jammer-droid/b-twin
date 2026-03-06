"""Runtime adapter implementations for attached/standalone modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from btwin.core.audit import AuditLogger
from btwin.core.runtime_ports import AuditEvent, AuditPort, MemoryEntry, MemoryRef, RecallPort, RecallQuery, RecallResult, VerificationReport


class OpenClawMemoryInterface(Protocol):
    def memory_search(self, *, query: str, scope: str, limit: int) -> list[dict[str, object]]: ...

    def memory_get(self, *, record_id: str) -> dict[str, object] | None: ...

    def memory_remember(
        self,
        *,
        content: str,
        tags: list[str],
        source: str,
        timestamp: datetime,
    ) -> dict[str, object]: ...


@dataclass(slots=True)
class StandaloneRecallAdapter(RecallPort):
    journal_path: Path

    def __post_init__(self) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def recall(self, query: RecallQuery) -> list[RecallResult]:
        if not self.journal_path.exists():
            return []

        hits: list[RecallResult] = []
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                import json

                row = json.loads(line)
            except Exception:
                continue

            content = str(row.get("content", ""))
            if query.query.lower() not in content.lower():
                continue

            record_id = str(row.get("record_id", ""))
            if not record_id:
                continue
            hits.append(
                RecallResult(
                    record_id=record_id,
                    summary=content[:160],
                    source=str(row.get("source", "standalone")),
                    confidence=0.5,
                    version=int(row.get("doc_version", 1)),
                    metadata={"tags": row.get("tags", [])},
                )
            )
            if len(hits) >= query.limit:
                break
        return hits

    def remember(
        self,
        entry: MemoryEntry,
        tags: list[str] | None = None,
        source: str | None = None,
        timestamp: datetime | None = None,
    ) -> MemoryRef:
        import json
        from uuid import uuid4

        record_id = f"mem_{uuid4().hex[:12]}"
        payload = {
            "record_id": record_id,
            "doc_version": entry.doc_version,
            "content": entry.content,
            "tags": tags or [],
            "source": source or "standalone",
            "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
        }
        with self.journal_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return MemoryRef(record_id=record_id, doc_version=entry.doc_version)


@dataclass(slots=True)
class OpenClawRecallAdapter(RecallPort):
    memory: OpenClawMemoryInterface

    def recall(self, query: RecallQuery) -> list[RecallResult]:
        rows = self.memory.memory_search(query=query.query, scope=query.scope, limit=query.limit)
        results: list[RecallResult] = []
        for row in rows:
            record_id = str(row.get("record_id") or row.get("id") or "")
            if not record_id:
                continue
            results.append(
                RecallResult(
                    record_id=record_id,
                    summary=str(row.get("summary") or row.get("content") or ""),
                    source=str(row.get("source") or "openclaw"),
                    confidence=float(row.get("confidence") or 0.0),
                    version=int(row.get("version") or row.get("doc_version") or 1),
                    metadata={"raw": row},
                )
            )
        return results

    def remember(
        self,
        entry: MemoryEntry,
        tags: list[str] | None = None,
        source: str | None = None,
        timestamp: datetime | None = None,
    ) -> MemoryRef:
        row = self.memory.memory_remember(
            content=entry.content,
            tags=tags or [],
            source=source or "btwin",
            timestamp=timestamp or datetime.now(UTC),
        )
        record_id = str(row.get("record_id") or row.get("id") or "")
        version = int(row.get("doc_version") or row.get("version") or entry.doc_version)
        return MemoryRef(record_id=record_id, doc_version=version)


@dataclass(slots=True)
class RuntimeAuditAdapter(AuditPort):
    logger: AuditLogger
    mode: str

    def append(self, event: AuditEvent) -> None:
        envelope = {
            "envelopeVersion": "1.0",
            "mode": self.mode,
            "actor": event.actor,
            "traceId": event.trace_id,
            "docVersion": event.doc_version,
            "checksum": event.checksum,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
        }
        self.logger.log(event_type=event.event_type, payload=envelope)

    def query(
        self,
        *,
        trace_id: str | None = None,
        actor: str | None = None,
        event_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[AuditEvent]:
        rows = self.logger.tail(limit=500)
        events: list[AuditEvent] = []
        for row in rows:
            if event_type and row.get("eventType") != event_type:
                continue
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if trace_id and payload.get("traceId") != trace_id:
                continue
            if actor and payload.get("actor") != actor:
                continue
            stamp = row.get("timestamp")
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else datetime.now(UTC)
            if time_range and not (time_range[0] <= dt <= time_range[1]):
                continue
            events.append(
                AuditEvent(
                    event_type=str(row.get("eventType")),
                    actor=str(payload.get("actor", "unknown")),
                    trace_id=str(payload.get("traceId", "")),
                    doc_version=int(payload.get("docVersion", 0)),
                    checksum=str(payload.get("checksum", "")),
                    payload=dict(payload.get("payload") or {}),
                    timestamp=dt,
                )
            )
        return events

    def verify_integrity(self, range_name: str) -> VerificationReport:
        _ = range_name
        return VerificationReport(ok=True)


@dataclass(slots=True)
class RuntimeAdapters:
    recall: RecallPort
    audit: RuntimeAuditAdapter


def build_runtime_adapters(
    *,
    mode: str,
    data_dir: Path,
    audit_logger: AuditLogger,
    openclaw_memory: OpenClawMemoryInterface | None = None,
) -> RuntimeAdapters:
    if mode == "attached" and openclaw_memory is not None:
        recall: RecallPort = OpenClawRecallAdapter(memory=openclaw_memory)
    else:
        recall = StandaloneRecallAdapter(journal_path=data_dir / "memory_journal.jsonl")

    audit = RuntimeAuditAdapter(logger=audit_logger, mode=mode)
    return RuntimeAdapters(recall=recall, audit=audit)
