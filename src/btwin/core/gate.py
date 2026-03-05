"""Gate validators and transition logic for collab workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from btwin.core.collab_models import CollabRecord, CollabStatus

GateErrorCode = Literal[
    "INVALID_STATE_TRANSITION",
    "CONCURRENT_MODIFICATION",
    "FORBIDDEN",
]

_ALLOWED_TRANSITIONS: dict[CollabStatus, set[CollabStatus]] = {
    "draft": {"handed_off", "completed"},
    "handed_off": {"completed"},
    "completed": set(),
}


@dataclass(frozen=True)
class GateDecision:
    ok: bool
    error_code: GateErrorCode | None = None
    message: str = ""
    idempotent: bool = False
    status: CollabStatus | None = None
    version: int | None = None
    details: dict[str, object] = field(default_factory=dict)


def validate_actor(actor_agent: str, allowed_agents: set[str]) -> GateDecision:
    if actor_agent in allowed_agents:
        return GateDecision(ok=True, status=None, version=None)

    return GateDecision(
        ok=False,
        error_code="FORBIDDEN",
        message="actor agent is not allowed",
        details={"actorAgent": actor_agent},
    )


def apply_transition(record: CollabRecord, target_status: CollabStatus, expected_version: int) -> GateDecision:
    if record.version != expected_version:
        return GateDecision(
            ok=False,
            error_code="CONCURRENT_MODIFICATION",
            message="expectedVersion does not match current version",
            details={"currentVersion": record.version, "expectedVersion": expected_version},
        )

    if record.status == target_status:
        return GateDecision(
            ok=True,
            idempotent=True,
            status=record.status,
            version=record.version,
            message="idempotent retry",
        )

    allowed_targets = _ALLOWED_TRANSITIONS.get(record.status, set())
    if target_status not in allowed_targets:
        return GateDecision(
            ok=False,
            error_code="INVALID_STATE_TRANSITION",
            message=f"cannot transition from {record.status} to {target_status}",
            details={"from": record.status, "to": target_status},
        )

    return GateDecision(ok=True, status=target_status, version=record.version + 1)
