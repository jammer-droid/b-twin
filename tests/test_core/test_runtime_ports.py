from dataclasses import dataclass

from btwin.core.runtime_ports import (
    ApprovalDecision,
    ApprovalPort,
    AuditEvent,
    AuditPort,
    IdentityPort,
    RecallPort,
    RecallQuery,
    RecallRecord,
)


@dataclass
class DummyRecall:
    def search(self, query: RecallQuery) -> list[RecallRecord]:
        return [RecallRecord(record_id="rec-1", summary=f"found:{query.query}")]


@dataclass
class DummyIdentity:
    def current_actor(self) -> str:
        return "main"


@dataclass
class DummyApproval:
    def request(self, action: str, actor: str, details: dict[str, object] | None = None) -> ApprovalDecision:
        return ApprovalDecision(approved=True, approver=actor, reason=action)


@dataclass
class DummyAudit:
    events: list[AuditEvent]

    def log(self, event: AuditEvent) -> None:
        self.events.append(event)


def test_protocol_assignability() -> None:
    recall: RecallPort = DummyRecall()
    identity: IdentityPort = DummyIdentity()
    approval: ApprovalPort = DummyApproval()
    audit: AuditPort = DummyAudit(events=[])

    assert recall.search(RecallQuery(query="hello"))[0].record_id == "rec-1"
    assert identity.current_actor() == "main"
    assert approval.request("promote", "main").approved is True

    event = AuditEvent(event_type="runtime.show", actor="main", payload={"mode": "attached"})
    audit.log(event)
    assert len(audit.events) == 1
