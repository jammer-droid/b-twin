from btwin.core.collab_models import CollabRecord
from btwin.core.gate import apply_transition, validate_actor


def _record(status: str = "draft", version: int = 1) -> CollabRecord:
    return CollabRecord.model_validate(
        {
            "recordId": "rec_01JNV2N5X6WQ4K3M2R1T9AZ8BY",
            "taskId": "jeonse-e2e-001",
            "recordType": "collab",
            "summary": "E2E 서버 충돌 원인 파악 및 수정",
            "evidence": ["tsx integration 11/11 pass"],
            "nextAction": ["CI 스크립트 정리"],
            "status": status,
            "authorAgent": "codex-code",
            "createdAt": "2026-03-05T15:54:00+09:00",
            "version": version,
        }
    )


def test_apply_transition_succeeds_for_allowed_move() -> None:
    decision = apply_transition(
        record=_record(status="draft", version=1),
        target_status="handed_off",
        expected_version=1,
    )

    assert decision.ok is True
    assert decision.status == "handed_off"
    assert decision.version == 2
    assert decision.idempotent is False


def test_apply_transition_returns_idempotent_when_same_status() -> None:
    decision = apply_transition(
        record=_record(status="completed", version=3),
        target_status="completed",
        expected_version=3,
    )

    assert decision.ok is True
    assert decision.idempotent is True
    assert decision.status == "completed"
    assert decision.version == 3


def test_apply_transition_rejects_invalid_transition() -> None:
    decision = apply_transition(
        record=_record(status="completed", version=3),
        target_status="handed_off",
        expected_version=3,
    )

    assert decision.ok is False
    assert decision.error_code == "INVALID_STATE_TRANSITION"


def test_apply_transition_rejects_version_conflict() -> None:
    decision = apply_transition(
        record=_record(status="draft", version=2),
        target_status="handed_off",
        expected_version=1,
    )

    assert decision.ok is False
    assert decision.error_code == "CONCURRENT_MODIFICATION"
    assert decision.details["currentVersion"] == 2


def test_validate_actor_rejects_unknown_actor() -> None:
    decision = validate_actor("unknown-agent", {"main", "codex-code", "research-bot"})

    assert decision.ok is False
    assert decision.error_code == "FORBIDDEN"
