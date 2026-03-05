"""Runtime integration ports (contracts only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(slots=True)
class RecallQuery:
    query: str
    limit: int = 5
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RecallRecord:
    record_id: str
    summary: str
    score: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ApprovalDecision:
    approved: bool
    approver: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    actor: str
    payload: dict[str, object] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class RecallPort(Protocol):
    def search(self, query: RecallQuery) -> list[RecallRecord]: ...


class IdentityPort(Protocol):
    def current_actor(self) -> str: ...


class ApprovalPort(Protocol):
    def request(self, action: str, actor: str, details: dict[str, object] | None = None) -> ApprovalDecision: ...


class AuditPort(Protocol):
    def log(self, event: AuditEvent) -> None: ...
