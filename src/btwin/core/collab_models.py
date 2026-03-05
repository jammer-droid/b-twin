"""Collaboration record models for orchestrator-first framework."""

from __future__ import annotations

from datetime import datetime, timezone
from secrets import randbits
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _CROCKFORD[value & 31]
        value >>= 5
    return "".join(chars)


def generate_record_id(now: datetime | None = None) -> str:
    """Generate a record id in `rec_<ULID>` shape.

    ULID consists of 48-bit timestamp + 80-bit randomness encoded in Crockford base32.
    """
    ts = now or datetime.now(timezone.utc)
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("`now` must be timezone-aware")

    timestamp_ms = int(ts.timestamp() * 1000)
    ulid_ts = _encode_crockford(timestamp_ms, 10)
    ulid_rand = _encode_crockford(randbits(80), 16)
    return f"rec_{ulid_ts}{ulid_rand}"


CollabStatus = Literal["draft", "handed_off", "completed"]


class CollabRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    record_id: str = Field(alias="recordId", pattern=r"^rec_[0-9A-HJKMNPQRSTVWXYZ]{26}$")
    task_id: str = Field(alias="taskId", min_length=1)
    record_type: Literal["collab"] = Field(alias="recordType")
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    next_action: list[str] = Field(alias="nextAction", min_length=1)
    status: CollabStatus
    author_agent: str = Field(alias="authorAgent", min_length=1)
    created_at: datetime = Field(alias="createdAt")
    version: int = Field(ge=1)

    @field_validator("task_id", "summary", "author_agent")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text fields must not be empty")
        return cleaned

    @field_validator("evidence", "next_action")
    @classmethod
    def _non_empty_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("items must not be empty")
        return cleaned

    @field_validator("created_at")
    @classmethod
    def _require_timezone_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("createdAt must be timezone-aware")
        return value
