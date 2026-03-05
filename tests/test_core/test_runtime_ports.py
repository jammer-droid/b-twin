from dataclasses import dataclass

from btwin.core.runtime_ports import (
    ApprovalPort,
    ApprovalStatus,
    ApprovalTicket,
    AuditEvent,
    AuditPort,
    AuthorizationDecision,
    IdentityPort,
    MemoryEntry,
    MemoryRef,
    RecallPort,
    RecallQuery,
    RecallResult,
    Subject,
    VerificationReport,
)


@dataclass
class DummyRecall:
    def recall(self, query: RecallQuery) -> list[RecallResult]:
        return [
            RecallResult(
                record_id="rec-1",
                summary=f"found:{query.query}",
                source="local",
                confidence=0.9,
                version=1,
            )
        ]

    def remember(
        self,
        entry: MemoryEntry,
        tags: list[str] | None = None,
        source: str | None = None,
        timestamp=None,
    ) -> MemoryRef:
        return MemoryRef(record_id="mem-1", doc_version=entry.doc_version + 1)


@dataclass
class DummyIdentity:
    def resolve_subject(self, subject_hint: str) -> Subject:
        return Subject(subject_id=subject_hint, roles=["main"])

    def authorize(self, subject: Subject, action: str, resource: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=True,
            policy_id="policy-main",
            decision_reason=f"{subject.subject_id}:{action}:{resource}",
            ttl=60,
        )


@dataclass
class DummyApproval:
    statuses: dict[str, ApprovalStatus]

    def request_approval(self, action: str, risk_level: str, context: dict[str, object]) -> ApprovalTicket:
        ticket = ApprovalTicket(ticket_id="t-1", status="PENDING")
        self.statuses[ticket.ticket_id] = ApprovalStatus(ticket_id=ticket.ticket_id, status="PENDING")
        return ticket

    def get_approval(self, ticket_id: str) -> ApprovalStatus:
        return self.statuses[ticket_id]

    def record_approval_decision(self, ticket_id: str, approver: str, decision, reason: str) -> None:
        self.statuses[ticket_id] = ApprovalStatus(ticket_id=ticket_id, status=decision, approver=approver, reason=reason)


@dataclass
class DummyAudit:
    events: list[AuditEvent]

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def query(self, *, trace_id=None, actor=None, event_type=None, time_range=None) -> list[AuditEvent]:
        return [
            e
            for e in self.events
            if (trace_id is None or e.trace_id == trace_id)
            and (actor is None or e.actor == actor)
            and (event_type is None or e.event_type == event_type)
        ]

    def verify_integrity(self, range_name: str) -> VerificationReport:
        return VerificationReport(ok=True)


def test_protocol_assignability() -> None:
    recall: RecallPort = DummyRecall()
    identity: IdentityPort = DummyIdentity()
    approval: ApprovalPort = DummyApproval(statuses={})
    audit: AuditPort = DummyAudit(events=[])

    assert recall.recall(RecallQuery(query="hello"))[0].record_id == "rec-1"
    memory_ref = recall.remember(MemoryEntry(content="x", doc_version=1), tags=["a"], source="cli")
    assert memory_ref.doc_version == 2

    subject = identity.resolve_subject("main")
    decision = identity.authorize(subject, "promote", "record/1")
    assert decision.allowed is True
    assert decision.policy_id == "policy-main"

    ticket = approval.request_approval("promote", "high", {"recordId": "r1"})
    assert approval.get_approval(ticket.ticket_id).status == "PENDING"
    approval.record_approval_decision(ticket.ticket_id, approver="main", decision="APPROVED", reason="ok")
    assert approval.get_approval(ticket.ticket_id).status == "APPROVED"

    event = AuditEvent(
        event_type="runtime.show",
        actor="main",
        trace_id="trc-1",
        doc_version=1,
        checksum="sha256:abc",
        payload={"mode": "attached"},
    )
    audit.append(event)
    assert len(audit.query(trace_id="trc-1")) == 1
    assert audit.verify_integrity("latest").ok is True
