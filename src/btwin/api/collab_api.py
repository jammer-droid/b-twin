"""HTTP API for VS1 collab workflow."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from btwin.config import BTwinConfig, load_config
from btwin.core.agent_registry import AgentRegistry
from btwin.core.collab_models import CollabRecord, CollabStatus, generate_record_id
from btwin.core.gate import apply_transition, validate_actor
from btwin.core.storage import Storage


class CreateCollabRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    task_id: str = Field(alias="taskId")
    record_type: str = Field(alias="recordType")
    summary: str
    evidence: list[str]
    next_action: list[str] = Field(alias="nextAction")
    status: CollabStatus
    author_agent: str = Field(alias="authorAgent")
    created_at: str = Field(alias="createdAt")


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    record_id: str = Field(alias="recordId")
    expected_version: int = Field(alias="expectedVersion", ge=1)
    from_agent: str = Field(alias="fromAgent")
    to_agent: str = Field(alias="toAgent")


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    record_id: str = Field(alias="recordId")
    expected_version: int = Field(alias="expectedVersion", ge=1)
    actor_agent: str = Field(alias="actorAgent")


class ReloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    actor_agent: str = Field(alias="actorAgent")
    override_path: str | None = Field(default=None, alias="overridePath")


def create_collab_app(
    data_dir: Path,
    *,
    initial_agents: set[str] | None = None,
    extra_agents: set[str] | None = None,
    openclaw_config_path: str | None = None,
    admin_token: str | None = None,
) -> FastAPI:
    app = FastAPI(title="B-TWIN Collab API", version="0.1")
    storage = Storage(data_dir)
    registry = AgentRegistry(
        config_path=Path(openclaw_config_path).expanduser() if openclaw_config_path else None,
        extra_agents=extra_agents,
        initial_agents=initial_agents,
    )
    idempotency_cache: dict[str, dict[str, str]] = {}

    def _trace_id() -> str:
        return f"trc_{uuid4().hex[:12]}"

    def _error(status_code: int, error_code: str, message: str, details: dict[str, object] | None = None) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "errorCode": error_code,
                "message": message,
                "details": details or {},
                "traceId": _trace_id(),
            },
        )

    def _payload_hash(payload: dict[str, object]) -> str:
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _same_tuple(record: CollabRecord, req: CreateCollabRecordRequest) -> bool:
        return (
            record.task_id == req.task_id
            and record.status == req.status
            and record.author_agent == req.author_agent
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(_request: Request, exc: RequestValidationError):
        return _error(
            422,
            "INVALID_SCHEMA",
            "request validation failed",
            {"issues": exc.errors()},
        )

    @app.post("/api/collab/records")
    def create_record(payload: CreateCollabRecordRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        allowed = registry.agents
        actor_decision = validate_actor(payload.author_agent, allowed)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", "author agent is not allowed", actor_decision.details)

        if payload.record_type != "collab":
            return _error(422, "INVALID_SCHEMA", "recordType must be collab")

        request_payload = payload.model_dump(by_alias=True, mode="json")
        request_hash = _payload_hash(request_payload)

        if idempotency_key:
            cached = idempotency_cache.get(idempotency_key)
            if cached:
                if cached["payload_hash"] != request_hash:
                    return _error(409, "DUPLICATE_RECORD", "idempotency key reused with different payload")

                existing = storage.read_collab_record(cached["record_id"])
                if existing is not None:
                    return {
                        "recordId": existing.record_id,
                        "status": existing.status,
                        "version": existing.version,
                        "idempotent": True,
                    }

        for existing in storage.list_collab_records():
            if _same_tuple(existing, payload):
                existing_payload = {
                    "taskId": existing.task_id,
                    "recordType": existing.record_type,
                    "summary": existing.summary,
                    "evidence": existing.evidence,
                    "nextAction": existing.next_action,
                    "status": existing.status,
                    "authorAgent": existing.author_agent,
                    "createdAt": existing.created_at.isoformat(),
                }
                if _payload_hash(existing_payload) != request_hash:
                    return _error(
                        409,
                        "DUPLICATE_RECORD",
                        "same taskId+status+authorAgent exists with different payload",
                        {
                            "taskId": payload.task_id,
                            "status": payload.status,
                            "authorAgent": payload.author_agent,
                        },
                    )
                return _error(
                    409,
                    "DUPLICATE_RECORD",
                    "same taskId+status+authorAgent already exists",
                    {
                        "recordId": existing.record_id,
                    },
                )

        try:
            record = CollabRecord.model_validate(
                {
                    **request_payload,
                    "recordId": generate_record_id(),
                    "version": 1,
                }
            )
        except ValidationError as exc:
            return _error(422, "INVALID_SCHEMA", "collab record validation failed", {"issues": exc.errors()})

        storage.save_collab_record(record)

        if idempotency_key:
            idempotency_cache[idempotency_key] = {
                "payload_hash": request_hash,
                "record_id": record.record_id,
            }

        return JSONResponse(
            status_code=201,
            content={
                "recordId": record.record_id,
                "status": record.status,
                "version": record.version,
                "idempotent": False,
            },
        )

    @app.get("/api/collab/records")
    def list_records(status: str | None = None, authorAgent: str | None = None, taskId: str | None = None):
        records = storage.list_collab_records()
        filtered: list[dict[str, object]] = []

        for r in records:
            if status and status != "all" and r.status != status:
                continue
            if authorAgent and r.author_agent != authorAgent:
                continue
            if taskId and r.task_id != taskId:
                continue
            filtered.append(r.model_dump(by_alias=True, mode="json"))

        return {"items": filtered}

    @app.get("/api/collab/records/{record_id}")
    def get_record(record_id: str):
        doc = storage.read_collab_record_document(record_id)
        if doc is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": record_id})
        return doc

    @app.post("/api/collab/handoff")
    def handoff(payload: HandoffRequest, x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent")):
        actor = x_actor_agent or payload.from_agent

        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.from_agent:
            return _error(403, "FORBIDDEN", "actor must match fromAgent", {"actorAgent": actor, "fromAgent": payload.from_agent})
        if not registry.is_allowed(payload.to_agent):
            return _error(403, "FORBIDDEN", "toAgent is not allowed", {"toAgent": payload.to_agent})

        record = storage.read_collab_record(payload.record_id)
        if record is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": payload.record_id})
        if record.author_agent != payload.from_agent:
            return _error(
                403,
                "FORBIDDEN",
                "fromAgent is not current record owner",
                {"recordOwner": record.author_agent, "fromAgent": payload.from_agent},
            )

        decision = apply_transition(record, "handed_off", payload.expected_version)
        if not decision.ok:
            return _error(409, decision.error_code or "GATE_REJECTED", decision.message, decision.details)

        if decision.idempotent:
            return {
                "recordId": record.record_id,
                "status": record.status,
                "version": record.version,
                "idempotent": True,
            }

        updated = storage.update_collab_record(
            payload.record_id,
            status=decision.status or "handed_off",
            version=decision.version or record.version,
            author_agent=payload.to_agent,
        )
        if updated is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": payload.record_id})

        return {
            "recordId": updated.record_id,
            "status": updated.status,
            "version": updated.version,
            "idempotent": False,
        }

    @app.post("/api/collab/complete")
    def complete(payload: CompleteRequest, x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent")):
        actor = x_actor_agent or payload.actor_agent
        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        record = storage.read_collab_record(payload.record_id)
        if record is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": payload.record_id})
        if record.author_agent != actor:
            return _error(
                403,
                "FORBIDDEN",
                "actor is not current record owner",
                {"recordOwner": record.author_agent, "actorAgent": actor},
            )

        decision = apply_transition(record, "completed", payload.expected_version)
        if not decision.ok:
            return _error(409, decision.error_code or "GATE_REJECTED", decision.message, decision.details)

        if decision.idempotent:
            return {
                "recordId": record.record_id,
                "status": record.status,
                "version": record.version,
                "idempotent": True,
            }

        updated = storage.update_collab_record(payload.record_id, status=decision.status or "completed", version=decision.version or record.version)
        if updated is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": payload.record_id})

        return {
            "recordId": updated.record_id,
            "status": updated.status,
            "version": updated.version,
            "idempotent": False,
        }

    @app.post("/api/admin/agents/reload")
    def reload_agents(payload: ReloadRequest, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        if not (payload.actor_agent == "main" or (admin_token and x_admin_token == admin_token)):
            return _error(403, "FORBIDDEN", "admin reload is restricted")

        summary = registry.reload(payload.override_path)
        return {"ok": True, **summary}

    return app


def create_default_collab_app() -> FastAPI:
    """Create API app from default B-TWIN/OpenClaw runtime config."""
    config_path = Path.home() / ".btwin" / "config.yaml"
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = BTwinConfig()

    extra_agents_env = os.environ.get("BTWIN_EXTRA_AGENTS", "")
    extra_agents = {a.strip() for a in extra_agents_env.split(",") if a.strip()}

    return create_collab_app(
        data_dir=config.data_dir,
        extra_agents=extra_agents,
        openclaw_config_path=os.environ.get("BTWIN_OPENCLAW_CONFIG_PATH"),
        admin_token=os.environ.get("BTWIN_ADMIN_TOKEN"),
    )
