"""HTTP API for VS1 collab workflow."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import OrderedDict
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from btwin.config import BTwinConfig, load_config
from btwin.core.agent_registry import AgentRegistry
from btwin.core.btwin import BTwin
from btwin.core.audit import AuditLogger
from btwin.core.collab_models import CollabRecord, CollabStatus, generate_record_id
from btwin.core.gate import apply_transition, validate_actor, validate_promotion_approval
from btwin.core.indexer import CoreIndexer
from btwin.core.promotion_store import (
    PromotionActorRequiredError,
    PromotionItemNotFoundError,
    PromotionStore,
    PromotionTransitionError,
)
from btwin.core.promotion_worker import PromotionWorker
from btwin.core.runtime_adapters import OpenClawMemoryInterface, build_runtime_adapters
from btwin.core.runtime_ports import AuditEvent
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
    project_id: str | None = Field(default=None, alias="projectId")


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


class ProposePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_record_id: str = Field(alias="sourceRecordId")
    proposed_by: str = Field(alias="proposedBy")


class ApprovePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    actor_agent: str = Field(alias="actorAgent")


class RunPromotionBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    actor_agent: str = Field(alias="actorAgent")
    limit: int | None = Field(default=None, ge=1, le=1000)


class IndexerActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    actor_agent: str = Field(alias="actorAgent")
    limit: int | None = Field(default=None, ge=1, le=1000)
    doc_id: str | None = Field(default=None, alias="docId")


# ---------------------------------------------------------------------------
# Proxy-facing entry/session models
# ---------------------------------------------------------------------------


class EntryRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    content: str
    topic: str | None = None
    project_id: str | None = Field(default=None, alias="projectId")


class EntrySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    query: str
    n_results: int = Field(default=5, alias="nResults", ge=1, le=100)
    project_id: str | None = Field(default=None, alias="projectId")
    record_type: str | None = Field(default=None, alias="recordType")
    scope: Literal["project", "all"] = "project"


class ConvoRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    content: str
    requested_by_user: bool = Field(default=False, alias="requestedByUser")
    topic: str | None = None
    project_id: str | None = Field(default=None, alias="projectId")


class EntryImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    content: str
    date: str
    slug: str
    tags: list[str] | None = None
    source_path: str | None = Field(default=None, alias="sourcePath")
    project_id: str | None = Field(default=None, alias="projectId")


class SessionStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    topic: str | None = None


class SessionEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    summary: str | None = None
    slug: str | None = None
    project_id: str | None = Field(default=None, alias="projectId")


def create_collab_app(
    data_dir: Path,
    *,
    runtime_mode: str = "attached",
    initial_agents: set[str] | None = None,
    extra_agents: set[str] | None = None,
    openclaw_config_path: str | None = None,
    openclaw_memory: OpenClawMemoryInterface | None = None,
    admin_token: str | None = None,
) -> FastAPI:
    app = FastAPI(title="B-TWIN Collab API", version="0.1")
    storage = Storage(data_dir)
    promotion_store = PromotionStore(data_dir / "promotion_queue.yaml")
    audit_logger = AuditLogger(data_dir / "audit.log.jsonl")
    if runtime_mode == "standalone" and initial_agents is None:
        initial_agents = {"main"}

    registry = AgentRegistry(
        config_path=Path(openclaw_config_path).expanduser() if openclaw_config_path else None,
        extra_agents=extra_agents,
        initial_agents=initial_agents,
    )
    runtime_adapters = build_runtime_adapters(
        mode=runtime_mode,
        data_dir=data_dir,
        audit_logger=audit_logger,
        openclaw_memory=openclaw_memory,
    )
    _IDEMPOTENCY_CACHE_MAX = 1000
    idempotency_cache: OrderedDict[str, dict[str, str]] = OrderedDict()

    def _foundation_router(scope: str) -> APIRouter:
        router = APIRouter(prefix=f"/api/{scope}", tags=[f"foundation:{scope}"])

        @router.get("/health")
        def foundation_health():
            return {
                "ok": True,
                "scope": scope,
                "status": "available",
            }

        return router

    for foundation_scope in ("workflows", "entries", "sources"):
        app.include_router(_foundation_router(foundation_scope))

    def _trace_id() -> str:
        return f"trc_{uuid4().hex[:12]}"

    def _audit(event_type: str, payload: dict[str, object]) -> None:
        runtime_adapters.audit.append(
            AuditEvent(
                event_type=event_type,
                actor=str(payload.get("actorAgent") or payload.get("actor") or "system"),
                trace_id=_trace_id(),
                doc_version=int(payload.get("docVersion") or 0),
                checksum=str(payload.get("checksum") or "n/a"),
                payload=payload,
            )
        )

    _indexer_cache: CoreIndexer | None = None

    def _indexer() -> CoreIndexer:
        nonlocal _indexer_cache
        if _indexer_cache is None:
            _indexer_cache = CoreIndexer(data_dir=data_dir)
        return _indexer_cache

    _btwin_cache: BTwin | None = None

    def _btwin() -> BTwin:
        nonlocal _btwin_cache
        if _btwin_cache is None:
            config = BTwinConfig(data_dir=data_dir)
            _btwin_cache = BTwin(config)
        return _btwin_cache

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

    def _require_admin_token_if_configured(x_admin_token: str | None) -> JSONResponse | None:
        if not admin_token:
            return None
        if x_admin_token and hmac.compare_digest(x_admin_token, admin_token):
            return None
        return _error(403, "FORBIDDEN", "admin token is required")

    def _require_main_admin(actor: str, x_admin_token: str | None) -> JSONResponse | None:
        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)

        approval_decision = validate_promotion_approval(actor)
        if not approval_decision.ok:
            return _error(403, "FORBIDDEN", approval_decision.message or "forbidden", approval_decision.details)

        return _require_admin_token_if_configured(x_admin_token)

    def _payload_hash(payload: dict[str, object]) -> str:
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _same_tuple(record: CollabRecord, req: CreateCollabRecordRequest) -> bool:
        return (
            record.task_id == req.task_id
            and record.status == req.status
            and record.author_agent == req.author_agent
        )

    def _enforce_integrity_gate(*, record_id: str, endpoint: str, actor: str) -> JSONResponse | None:
        doc = storage.collab_index_doc_info(record_id)
        if doc is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": record_id})

        idx = _indexer()
        existing = idx.manifest.get(doc["doc_id"])
        already_healthy = (
            existing is not None
            and existing.status == "indexed"
            and existing.checksum == doc["checksum"]
        )
        if not already_healthy:
            idx.mark_pending(
                doc_id=doc["doc_id"],
                path=doc["path"],
                record_type="collab",
                checksum=doc["checksum"],
            )

        integrity = idx.verify_doc_integrity(doc["doc_id"])
        repair_attempts = 0
        max_retries = 2
        last_repair: dict[str, object] | None = None

        while not integrity.get("ok") and repair_attempts < max_retries:
            last_repair = idx.repair(doc["doc_id"])
            repair_attempts += 1
            integrity = idx.verify_doc_integrity(doc["doc_id"])

        if integrity.get("ok"):
            return None

        details = {
            "recordId": record_id,
            "docId": doc["doc_id"],
            "integrity": integrity,
            "repairAttempts": repair_attempts,
            "lastRepair": last_repair or {},
        }
        _audit(
            "gate_rejected",
            {
                "endpoint": endpoint,
                "errorCode": "INTEGRITY_GATE_FAILED",
                "recordId": record_id,
                "actorAgent": actor,
                "details": details,
            },
        )
        return _error(409, "INTEGRITY_GATE_FAILED", "index integrity gate failed", details)

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(_request: Request, exc: RequestValidationError):
        return _error(
            422,
            "INVALID_SCHEMA",
            "request validation failed",
            {"issues": exc.errors()},
        )

    def _foundation_ui_shell_html() -> str:
        return """
<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B-TWIN Shared Shell</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }
    h1 { margin: 0 0 8px; }
    p { color: #475569; }
    nav { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }
    a { color: #0f172a; text-decoration: none; border: 1px solid #cbd5e1; border-radius: 999px; padding: 8px 12px; }
    a:hover { background: #f8fafc; }
    .panel { border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; background: #fff; }
    ul { margin: 12px 0 0; padding-left: 20px; color: #475569; }
  </style>
</head>
<body>
  <h1>B-TWIN shared shell</h1>
  <p>Minimal foundation navigation for workflow and dashboard features.</p>
  <nav aria-label=\"foundation\">
    <a href=\"/ui/workflows\">workflows</a>
    <a href=\"/ui/entries\">entries</a>
    <a href=\"/ui/sources\">sources</a>
    <a href=\"/ui/summary\">summary</a>
    <a href=\"/ops\">ops</a>
  </nav>
  <section class=\"panel\">
    <strong>shared shell only</strong>
    <ul>
      <li>feature pages can plug in behind these routes later</li>
      <li>existing entries and ops screens remain available</li>
      <li>workflows, sources, and summary stay intentionally lightweight for now</li>
    </ul>
  </section>
</body>
</html>
        """

    @app.get("/ui", response_class=HTMLResponse)
    def foundation_ui_shell() -> str:
        return _foundation_ui_shell_html()

    def _placeholder_ui_html(title: str, description: str) -> str:
        return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }}
    .panel {{ max-width: 720px; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }}
    a {{ color: #0f172a; }}
    p {{ color: #475569; }}
  </style>
</head>
<body>
  <div class=\"panel\">
    <h1>{title}</h1>
    <p>{description}</p>
    <p><a href=\"/ui\">Back to shared shell</a></p>
  </div>
</body>
</html>
        """

    @app.get("/ui/workflows", response_class=HTMLResponse)
    def workflows_ui_placeholder() -> str:
        return _placeholder_ui_html(
            "Workflows",
            "Workflow orchestration UI placeholder for the common foundation shell.",
        )

    @app.get("/ui/sources", response_class=HTMLResponse)
    def sources_ui_placeholder() -> str:
        return _placeholder_ui_html(
            "Sources",
            "Source inventory UI placeholder for the common foundation shell.",
        )

    @app.get("/ui/summary", response_class=HTMLResponse)
    def summary_ui_placeholder() -> str:
        return _placeholder_ui_html(
            "Summary",
            "Summary UI placeholder for the common foundation shell.",
        )

    def _ui_html() -> str:
        return """
<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B-TWIN Collab Dashboard</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }
    h1 { margin: 0 0 16px; }
    .layout { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
    .card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }
    tr:hover { background: #f8fafc; cursor: pointer; }
    .muted { color: #64748b; font-size: 12px; }
    .status { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid #cbd5e1; }
    .status.draft { background: #fff7ed; }
    .status.handed_off { background: #eff6ff; }
    .status.completed { background: #f0fdf4; }
    .toolbar { display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }
    .error { margin-top: 12px; padding: 10px; border: 1px solid #fecaca; background: #fef2f2; color: #991b1b; display: none; }
    input, select, button { font-size: 14px; padding: 6px 8px; }
    button { border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; cursor: pointer; }
    .actions { display: grid; gap: 8px; margin-top: 12px; }
  </style>
</head>
<body>
  <h1>Collab Records</h1>
  <div class=\"layout\">
    <section class=\"card\">
      <div class=\"toolbar\">
        <label for=\"statusFilter\">상태 필터</label>
        <select id=\"statusFilter\">
          <option value=\"in-progress\" selected>진행중(draft + handed_off)</option>
          <option value=\"all\">전체</option>
          <option value=\"draft\">draft</option>
          <option value=\"handed_off\">handed_off</option>
          <option value=\"completed\">completed</option>
        </select>
        <button id=\"refreshBtn\">새로고침</button>
      </div>
      <table>
        <thead><tr><th>taskId</th><th>status</th><th>authorAgent</th><th>createdAt</th></tr></thead>
        <tbody id=\"recordsBody\"></tbody>
      </table>
    </section>
    <aside class=\"card\">
      <h3>상세</h3>
      <div id=\"detail\" class=\"muted\">레코드를 선택하세요.</div>
      <div class=\"actions\">
        <div>
          <div class=\"muted\">handoff</div>
          <input id=\"handoffFrom\" placeholder=\"fromAgent\" />
          <input id=\"handoffTo\" placeholder=\"toAgent\" />
          <input id=\"handoffVersion\" placeholder=\"expectedVersion\" type=\"number\" min=\"1\" />
          <button id=\"handoffBtn\">handoff 실행</button>
        </div>
        <div>
          <div class=\"muted\">complete</div>
          <input id=\"completeActor\" placeholder=\"actorAgent\" />
          <input id=\"completeVersion\" placeholder=\"expectedVersion\" type=\"number\" min=\"1\" />
          <button id=\"completeBtn\">complete 실행</button>
        </div>
      </div>
      <div id=\"errorPanel\" class=\"error\"></div>
    </aside>
  </div>

  <script>
    const state = { items: [], selected: null };

    function escapeHtml(v) {
      return String(v ?? '').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    async function loadRecords() {
      const res = await fetch('/api/collab/records');
      const data = await res.json();
      state.items = data.items || [];
      renderTable();
    }

    function matchesFilter(item, filter) {
      if (filter === 'all') return true;
      if (filter === 'in-progress') return item.status === 'draft' || item.status === 'handed_off';
      return item.status === filter;
    }

    function renderTable() {
      const filter = document.getElementById('statusFilter').value;
      const body = document.getElementById('recordsBody');
      const rows = state.items
        .filter(item => matchesFilter(item, filter))
        .map(item => `
          <tr data-id=\"${escapeHtml(item.recordId)}\">
            <td>${escapeHtml(item.taskId)}</td>
            <td><span class=\"status ${escapeHtml(item.status)}\">${escapeHtml(item.status)}</span></td>
            <td>${escapeHtml(item.authorAgent)}</td>
            <td>${escapeHtml(item.createdAt)}</td>
          </tr>
        `)
        .join('');
      body.innerHTML = rows || '<tr><td colspan=\"4\" class=\"muted\">데이터 없음</td></tr>';
      for (const tr of body.querySelectorAll('tr[data-id]')) {
        tr.addEventListener('click', () => selectRecord(tr.dataset.id));
      }
    }

    function setError(message, traceId) {
      const panel = document.getElementById('errorPanel');
      if (!message) {
        panel.style.display = 'none';
        panel.textContent = '';
        return;
      }
      panel.style.display = 'block';
      panel.innerHTML = `<strong>${escapeHtml(message)}</strong><div class=\"muted\">traceId: ${escapeHtml(traceId || '-')}</div>`;
    }

    async function selectRecord(recordId) {
      setError('');
      const res = await fetch(`/api/collab/records/${recordId}`);
      const data = await res.json();
      if (!res.ok) {
        setError(data.message, data.traceId);
        return;
      }
      state.selected = data;
      const fm = data.frontmatter;
      document.getElementById('detail').innerHTML = `
        <div><strong>${escapeHtml(fm.taskId)}</strong></div>
        <div class=\"muted\">recordId: ${escapeHtml(fm.recordId)}</div>
        <pre>${escapeHtml(data.content)}</pre>
      `;
      document.getElementById('handoffFrom').value = fm.authorAgent || '';
      document.getElementById('completeActor').value = fm.authorAgent || '';
      document.getElementById('handoffVersion').value = String(fm.version || 1);
      document.getElementById('completeVersion').value = String(fm.version || 1);
    }

    async function runHandoff() {
      if (!state.selected) return;
      const fm = state.selected.frontmatter;
      const payload = {
        recordId: fm.recordId,
        expectedVersion: Number(document.getElementById('handoffVersion').value || fm.version),
        fromAgent: document.getElementById('handoffFrom').value,
        toAgent: document.getElementById('handoffTo').value,
      };
      const actor = payload.fromAgent;
      const res = await fetch('/api/collab/handoff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Actor-Agent': actor },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message, data.traceId);
        return;
      }
      await loadRecords();
      await selectRecord(payload.recordId);
    }

    async function runComplete() {
      if (!state.selected) return;
      const fm = state.selected.frontmatter;
      const payload = {
        recordId: fm.recordId,
        expectedVersion: Number(document.getElementById('completeVersion').value || fm.version),
        actorAgent: document.getElementById('completeActor').value,
      };
      const res = await fetch('/api/collab/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Actor-Agent': payload.actorAgent },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message, data.traceId);
        return;
      }
      await loadRecords();
      await selectRecord(payload.recordId);
    }

    document.getElementById('refreshBtn').addEventListener('click', loadRecords);
    document.getElementById('statusFilter').addEventListener('change', renderTable);
    document.getElementById('handoffBtn').addEventListener('click', runHandoff);
    document.getElementById('completeBtn').addEventListener('click', runComplete);

    loadRecords();
  </script>
</body>
</html>
        """

    @app.get("/ui/collab", response_class=HTMLResponse)
    def collab_ui() -> str:
        return _ui_html()

    def _promotions_ui_html() -> str:
        return """
<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B-TWIN Promotions Dashboard</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }
    h1 { margin: 0 0 16px; }
    .toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }
    .status { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid #cbd5e1; }
    .status.proposed { background: #fff7ed; }
    .status.approved { background: #eff6ff; }
    .status.queued { background: #f5f3ff; }
    .status.promoted { background: #f0fdf4; }
    button { border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; padding: 4px 8px; cursor: pointer; }
    .error { margin-top: 12px; padding: 10px; border: 1px solid #fecaca; background: #fef2f2; color: #991b1b; display: none; }
  </style>
</head>
<body>
  <h1>Promotions</h1>
  <div class=\"toolbar\">
    <label for=\"statusFilter\">상태</label>
    <select id=\"statusFilter\">
      <option value=\"proposed\" selected>proposed</option>
      <option value=\"approved\">approved</option>
      <option value=\"queued\">queued</option>
      <option value=\"promoted\">promoted</option>
      <option value=\"all\">all</option>
    </select>
    <input id=\"actorInput\" placeholder=\"actor(main)\" value=\"main\" />
    <button id=\"refreshBtn\">새로고침</button>
  </div>

  <table>
    <thead>
      <tr><th>itemId</th><th>sourceRecordId</th><th>status</th><th>proposedBy</th><th>action</th></tr>
    </thead>
    <tbody id=\"promotionsBody\"></tbody>
  </table>

  <div id=\"errorPanel\" class=\"error\"></div>

  <script>
    function esc(v) {
      return String(v ?? '').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    function showError(message, traceId) {
      const el = document.getElementById('errorPanel');
      if (!message) {
        el.style.display = 'none';
        el.textContent = '';
        return;
      }
      el.style.display = 'block';
      el.innerHTML = `<strong>${esc(message)}</strong><div>traceId: ${esc(traceId || '-')}</div>`;
    }

    async function loadPromotions() {
      showError('');
      const status = document.getElementById('statusFilter').value;
      const q = status === 'all' ? '' : `?status=${encodeURIComponent(status)}`;
      const res = await fetch(`/api/promotions${q}`);
      const data = await res.json();

      const items = data.items || [];
      const rows = items.map(item => {
        const approveBtn = item.status === 'proposed'
          ? `<button data-approve=\"${esc(item.itemId)}\">approve</button>`
          : '';

        return `
          <tr>
            <td>${esc(item.itemId)}</td>
            <td>${esc(item.sourceRecordId)}</td>
            <td><span class=\"status ${esc(item.status)}\">${esc(item.status)}</span></td>
            <td>${esc(item.proposedBy)}</td>
            <td>${approveBtn}</td>
          </tr>
        `;
      }).join('');

      const body = document.getElementById('promotionsBody');
      body.innerHTML = rows || '<tr><td colspan=\"5\">데이터 없음</td></tr>';

      body.querySelectorAll('button[data-approve]').forEach(btn => {
        btn.addEventListener('click', () => approve(btn.getAttribute('data-approve')));
      });
    }

    async function approve(itemId) {
      showError('');
      const actor = document.getElementById('actorInput').value;
      const res = await fetch(`/api/promotions/${encodeURIComponent(itemId)}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Actor-Agent': actor,
        },
        body: JSON.stringify({ actorAgent: actor }),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.message, data.traceId);
        return;
      }
      await loadPromotions();
    }

    document.getElementById('refreshBtn').addEventListener('click', loadPromotions);
    document.getElementById('statusFilter').addEventListener('change', loadPromotions);
    loadPromotions();
  </script>
</body>
</html>
        """

    @app.get("/ui/promotions", response_class=HTMLResponse)
    def promotions_ui() -> str:
        return _promotions_ui_html()

    def _promoted_ui_html() -> str:
        return """
<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B-TWIN Promoted History</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }
    h1 { margin: 0 0 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }
    .muted { color: #64748b; }
    .error { margin-top: 12px; padding: 10px; border: 1px solid #fecaca; background: #fef2f2; color: #991b1b; display: none; }
  </style>
</head>
<body>
  <h1>Promoted History</h1>
  <table>
    <thead><tr><th>itemId</th><th>sourceRecordId</th><th>scope</th><th>path</th></tr></thead>
    <tbody id=\"historyBody\"></tbody>
  </table>
  <div id=\"errorPanel\" class=\"error\"></div>

  <script>
    function esc(v) {
      return String(v ?? '').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[m]));
    }

    function showError(message, traceId) {
      const el = document.getElementById('errorPanel');
      if (!message) {
        el.style.display = 'none';
        el.textContent = '';
        return;
      }
      el.style.display = 'block';
      el.innerHTML = `<strong>${esc(message)}</strong><div class=\"muted\">traceId: ${esc(traceId || '-')}</div>`;
    }

    async function loadHistory() {
      const res = await fetch('/api/promotions/history');
      const data = await res.json();
      if (!res.ok) {
        showError(data.message, data.traceId);
        return;
      }

      const rows = (data.items || []).map(item => `
        <tr>
          <td>${esc(item.itemId)}</td>
          <td>${esc(item.sourceRecordId)}</td>
          <td>${esc(item.scope)}</td>
          <td class=\"muted\">${esc(item.path)}</td>
        </tr>
      `).join('');

      document.getElementById('historyBody').innerHTML = rows || '<tr><td colspan=\"4\" class=\"muted\">데이터 없음</td></tr>';
    }

    loadHistory();
  </script>
</body>
</html>
        """

    @app.get("/ui/promoted", response_class=HTMLResponse)
    def promoted_ui() -> str:
        return _promoted_ui_html()

    def _entries_ui_html() -> str:
        return """
<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B-TWIN Entries</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #0f172a; }
    h1 { margin: 0 0 16px; }
    .toolbar { display:flex; gap:8px; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }
  </style>
</head>
<body>
  <h1>Entries</h1>
  <div class=\"toolbar\">
    <label for=\"recordTypeFilter\">recordType</label>
    <select id=\"recordTypeFilter\">
      <option value=\"all\" selected>all</option>
      <option value=\"entry\">entry</option>
      <option value=\"collab\">collab</option>
      <option value=\"convo\">convo</option>
    </select>
    <button id=\"refreshBtn\">새로고침</button>
  </div>

  <table>
    <thead><tr><th>recordType</th><th>id/slug</th><th>date</th><th>summary</th></tr></thead>
    <tbody id=\"entriesBody\"></tbody>
  </table>

  <script>
    function esc(v) {
      return String(v ?? '').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[m]));
    }

    async function loadEntries() {
      const type = document.getElementById('recordTypeFilter').value;
      const q = type === 'all' ? '' : `?recordType=${encodeURIComponent(type)}`;
      const res = await fetch(`/api/entries${q}`);
      const data = await res.json();

      const rows = (data.items || []).map(item => `
        <tr>
          <td>${esc(item.recordType)}</td>
          <td>${esc(item.recordId || item.slug)}</td>
          <td>${esc(item.date)}</td>
          <td>${esc(item.summary || '')}</td>
        </tr>
      `).join('');

      document.getElementById('entriesBody').innerHTML = rows || '<tr><td colspan=\"4\">데이터 없음</td></tr>';
    }

    document.getElementById('refreshBtn').addEventListener('click', loadEntries);
    document.getElementById('recordTypeFilter').addEventListener('change', loadEntries);
    loadEntries();
  </script>
</body>
</html>
        """

    @app.get("/ui/entries", response_class=HTMLResponse)
    def entries_ui() -> str:
        return _entries_ui_html()

    @app.get("/api/entries")
    def list_entries(recordType: str | None = None, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        auth_error = _require_admin_token_if_configured(x_admin_token)
        if auth_error is not None:
            return auth_error

        items: list[dict[str, object]] = []

        if recordType in (None, "all", "entry"):
            for e in storage.list_entries():
                items.append(
                    {
                        "recordType": "entry",
                        "date": e.date,
                        "slug": e.slug,
                        "summary": e.content.split("\n", 1)[0][:120],
                    }
                )

        if recordType in (None, "all", "convo"):
            for e in storage.list_convo_entries():
                items.append(
                    {
                        "recordType": "convo",
                        "date": e.date,
                        "slug": e.slug,
                        "summary": e.content.split("\n", 1)[0][:120],
                    }
                )

        if recordType in (None, "all", "collab"):
            for c in storage.list_collab_records():
                items.append(
                    {
                        "recordType": "collab",
                        "date": c.created_at.date().isoformat(),
                        "recordId": c.record_id,
                        "summary": c.summary,
                    }
                )

        return {"items": items}

    @app.post("/api/collab/records")
    def create_record(payload: CreateCollabRecordRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        allowed = registry.agents
        actor_decision = validate_actor(payload.author_agent, allowed)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", "author agent is not allowed", actor_decision.details)

        if payload.record_type != "collab":
            return _error(422, "INVALID_SCHEMA", "recordType must be collab")

        request_payload = payload.model_dump(by_alias=True, mode="json", exclude={"project_id"})
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

        storage.save_collab_record(record, project=payload.project_id)

        if idempotency_key:
            idempotency_cache[idempotency_key] = {
                "payload_hash": request_hash,
                "record_id": record.record_id,
            }
            if len(idempotency_cache) >= _IDEMPOTENCY_CACHE_MAX:
                idempotency_cache.popitem(last=False)

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
    def list_records(status: str | None = None, authorAgent: str | None = None, taskId: str | None = None, projectId: str | None = None):
        records = storage.list_collab_records(project=projectId)
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

        integrity_error = _enforce_integrity_gate(record_id=payload.record_id, endpoint="/api/collab/handoff", actor=actor)
        if integrity_error is not None:
            return integrity_error

        decision = apply_transition(record, "handed_off", payload.expected_version)
        if not decision.ok:
            _audit(
                "gate_rejected",
                {
                    "endpoint": "/api/collab/handoff",
                    "errorCode": decision.error_code or "GATE_REJECTED",
                    "recordId": payload.record_id,
                    "actorAgent": actor,
                    "details": decision.details,
                },
            )
            return _error(409, decision.error_code or "GATE_REJECTED", decision.message, decision.details)

        if decision.idempotent:
            _audit(
                "gate_handoff_succeeded",
                {
                    "recordId": record.record_id,
                    "actorAgent": actor,
                    "fromStatus": record.status,
                    "toStatus": record.status,
                    "version": record.version,
                    "idempotent": True,
                },
            )
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

        _audit(
            "gate_handoff_succeeded",
            {
                "recordId": updated.record_id,
                "actorAgent": actor,
                "fromStatus": record.status,
                "toStatus": updated.status,
                "version": updated.version,
                "idempotent": False,
            },
        )
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

        integrity_error = _enforce_integrity_gate(record_id=payload.record_id, endpoint="/api/collab/complete", actor=actor)
        if integrity_error is not None:
            return integrity_error

        decision = apply_transition(record, "completed", payload.expected_version)
        if not decision.ok:
            _audit(
                "gate_rejected",
                {
                    "endpoint": "/api/collab/complete",
                    "errorCode": decision.error_code or "GATE_REJECTED",
                    "recordId": payload.record_id,
                    "actorAgent": actor,
                    "details": decision.details,
                },
            )
            return _error(409, decision.error_code or "GATE_REJECTED", decision.message, decision.details)

        if decision.idempotent:
            _audit(
                "gate_complete_succeeded",
                {
                    "recordId": record.record_id,
                    "actorAgent": actor,
                    "fromStatus": record.status,
                    "toStatus": record.status,
                    "version": record.version,
                    "idempotent": True,
                },
            )
            return {
                "recordId": record.record_id,
                "status": record.status,
                "version": record.version,
                "idempotent": True,
            }

        updated = storage.update_collab_record(payload.record_id, status=decision.status or "completed", version=decision.version or record.version)
        if updated is None:
            return _error(404, "RECORD_NOT_FOUND", "collab record not found", {"recordId": payload.record_id})

        _audit(
            "gate_complete_succeeded",
            {
                "recordId": updated.record_id,
                "actorAgent": actor,
                "fromStatus": record.status,
                "toStatus": updated.status,
                "version": updated.version,
                "idempotent": False,
            },
        )
        return {
            "recordId": updated.record_id,
            "status": updated.status,
            "version": updated.version,
            "idempotent": False,
        }

    @app.post("/api/promotions/propose")
    def propose_promotion(payload: ProposePromotionRequest, x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent")):
        actor = x_actor_agent or payload.proposed_by

        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.proposed_by:
            return _error(403, "FORBIDDEN", "actor must match proposedBy", {"actorAgent": actor, "proposedBy": payload.proposed_by})

        if storage.read_collab_record(payload.source_record_id) is None:
            return _error(404, "RECORD_NOT_FOUND", "source collab record not found", {"sourceRecordId": payload.source_record_id})

        item = promotion_store.enqueue(source_record_id=payload.source_record_id, proposed_by=payload.proposed_by)
        _audit(
            "promotion_proposed",
            {
                "itemId": item.item_id,
                "sourceRecordId": item.source_record_id,
                "proposedBy": item.proposed_by,
            },
        )
        return JSONResponse(
            status_code=201,
            content={
                "itemId": item.item_id,
                "sourceRecordId": item.source_record_id,
                "status": item.status,
                "proposedBy": item.proposed_by,
                "proposedAt": item.proposed_at.isoformat(),
            },
        )

    @app.get("/api/promotions")
    def list_promotions(status: str | None = None):
        items = promotion_store.list_items(status=status if status else None)
        return {
            "items": [
                {
                    "itemId": item.item_id,
                    "sourceRecordId": item.source_record_id,
                    "status": item.status,
                    "proposedBy": item.proposed_by,
                    "proposedAt": item.proposed_at.isoformat(),
                    "approvedBy": item.approved_by,
                    "approvedAt": item.approved_at.isoformat() if item.approved_at else None,
                    "queuedAt": item.queued_at.isoformat() if item.queued_at else None,
                    "promotedAt": item.promoted_at.isoformat() if item.promoted_at else None,
                }
                for item in items
            ]
        }

    @app.post("/api/promotions/{item_id}/approve")
    def approve_promotion(
        item_id: str,
        payload: ApprovePromotionRequest,
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
    ):
        actor = x_actor_agent or payload.actor_agent

        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        approval_decision = validate_promotion_approval(actor)
        if not approval_decision.ok:
            return _error(403, "FORBIDDEN", approval_decision.message or "forbidden", approval_decision.details)

        try:
            item = promotion_store.set_status(item_id, "approved", actor=actor)
        except PromotionItemNotFoundError:
            return _error(404, "PROMOTION_NOT_FOUND", "promotion item not found", {"itemId": item_id})
        except PromotionActorRequiredError:
            return _error(422, "INVALID_SCHEMA", "actor is required for approval")
        except PromotionTransitionError as exc:
            return _error(409, "INVALID_STATE_TRANSITION", str(exc), {"itemId": item_id})

        _audit(
            "promotion_approved",
            {
                "itemId": item.item_id,
                "approvedBy": item.approved_by or actor,
            },
        )
        return {
            "itemId": item.item_id,
            "status": item.status,
            "approvedBy": item.approved_by,
            "approvedAt": item.approved_at.isoformat() if item.approved_at else None,
        }

    @app.post("/api/promotions/run-batch")
    def run_promotions_batch(
        payload: RunPromotionBatchRequest,
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        actor = x_actor_agent or payload.actor_agent

        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        approval_decision = validate_promotion_approval(actor)
        if not approval_decision.ok:
            return _error(403, "FORBIDDEN", approval_decision.message or "forbidden", approval_decision.details)

        if not admin_token:
            return _error(403, "FORBIDDEN", "batch run is disabled (no admin token configured)")
        if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
            return _error(403, "FORBIDDEN", "admin token is required")

        worker = PromotionWorker(storage=storage, promotion_store=promotion_store, indexer=_indexer())
        result = worker.run_once(limit=payload.limit)
        _audit(
            "promotion_batch_run",
            {
                "actorAgent": actor,
                "limit": payload.limit,
                **result,
            },
        )
        return result

    @app.get("/api/promotions/history")
    def promotions_history(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        auth_error = _require_admin_token_if_configured(x_admin_token)
        if auth_error is not None:
            return auth_error
        return {"items": storage.list_promoted_entries()}

    @app.get("/api/indexer/status")
    def indexer_status(projectId: str | None = None, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        auth_error = _require_admin_token_if_configured(x_admin_token)
        if auth_error is not None:
            return auth_error
        return _indexer().status_summary(project=projectId)

    @app.get("/api/indexer/kpi")
    def indexer_kpi(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        auth_error = _require_admin_token_if_configured(x_admin_token)
        if auth_error is not None:
            return auth_error
        return _indexer().kpi_summary()

    @app.get("/api/ops/dashboard")
    def ops_dashboard(projectId: str | None = None, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
        auth_error = _require_admin_token_if_configured(x_admin_token)
        if auth_error is not None:
            return auth_error

        idx = _indexer()
        gate_violations = [
            row
            for row in audit_logger.tail(limit=200)
            if row.get("eventType") == "gate_rejected"
        ]
        return {
            "runtime": {
                "mode": runtime_mode,
                "attached": runtime_mode == "attached",
                "recallAdapter": runtime_adapters.recall_backend,
                "degraded": runtime_adapters.degraded,
                "degradedReason": runtime_adapters.degraded_reason,
            },
            "indexerStatus": idx.status_summary(project=projectId),
            "failureQueue": idx.failure_queue(limit=50),
            "repairHistory": idx.repair_history(limit=20),
            "gateViolations": gate_violations[-20:],
        }

    @app.get("/ops")
    def ops_dashboard_ui():
        return HTMLResponse(
            """
<!doctype html><html><head><meta charset='utf-8'><title>B-TWIN Ops</title></head>
<body>
<h1>B-TWIN Ops Dashboard</h1>
<label for='admin-token'>Admin token (optional)</label>
<input id='admin-token' type='password' placeholder='X-Admin-Token' />
<button id='load-btn' type='button'>Load</button>
<pre id='out'>loading...</pre>
<script>
async function loadDashboard() {
  const token = document.getElementById('admin-token').value.trim();
  const headers = token ? {'X-Admin-Token': token} : {};
  try {
    const res = await fetch('/api/ops/dashboard', {headers});
    const body = await res.json();
    if (!res.ok) {
      document.getElementById('out').textContent = 'failed (' + res.status + '): ' + JSON.stringify(body, null, 2);
      return;
    }
    document.getElementById('out').textContent = JSON.stringify(body, null, 2);
  } catch (err) {
    document.getElementById('out').textContent = 'failed: ' + String(err);
  }
}

document.getElementById('load-btn').addEventListener('click', loadDashboard);
loadDashboard();
</script>
</body></html>
            """
        )

    @app.post("/api/indexer/refresh")
    def indexer_refresh(
        payload: IndexerActionRequest,
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        actor = x_actor_agent or payload.actor_agent
        auth_error = _require_main_admin(actor, x_admin_token)
        if auth_error is not None:
            return auth_error
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        result = _indexer().refresh(limit=payload.limit)
        _audit("indexer_refresh", {"actorAgent": actor, **result})
        return result

    @app.post("/api/indexer/reconcile")
    def indexer_reconcile(
        payload: IndexerActionRequest,
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        actor = x_actor_agent or payload.actor_agent
        auth_error = _require_main_admin(actor, x_admin_token)
        if auth_error is not None:
            return auth_error
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        result = _indexer().reconcile()
        _audit("indexer_reconcile", {"actorAgent": actor, **result})
        return result

    @app.post("/api/indexer/repair")
    def indexer_repair(
        payload: IndexerActionRequest,
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        actor = x_actor_agent or payload.actor_agent
        auth_error = _require_main_admin(actor, x_admin_token)
        if auth_error is not None:
            return auth_error
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})
        if not payload.doc_id:
            return _error(422, "INVALID_SCHEMA", "docId is required")

        result = _indexer().repair(payload.doc_id)
        _audit("indexer_repair", {"actorAgent": actor, **result})
        return result

    @app.post("/api/admin/agents/reload")
    def reload_agents(
        payload: ReloadRequest,
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
        x_actor_agent: str | None = Header(default=None, alias="X-Actor-Agent"),
    ):
        actor = x_actor_agent or payload.actor_agent

        actor_decision = validate_actor(actor, registry.agents)
        if not actor_decision.ok:
            return _error(403, "FORBIDDEN", actor_decision.message or "forbidden", actor_decision.details)
        if actor != payload.actor_agent:
            return _error(403, "FORBIDDEN", "actor must match actorAgent", {"actorAgent": actor})

        if not admin_token:
            return _error(403, "FORBIDDEN", "admin reload is disabled (no admin token configured)")
        if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
            return _error(403, "FORBIDDEN", "admin token is required")

        if payload.override_path:
            resolved = Path(payload.override_path).expanduser().resolve()
            home_dir = Path.home().resolve()
            if not resolved.is_relative_to(home_dir):
                return _error(
                    400,
                    "INVALID_PATH",
                    "overridePath must resolve within the user home directory",
                )

        summary = registry.reload(payload.override_path)
        return {"ok": True, **summary}

    # -----------------------------------------------------------------------
    # Proxy-facing entry/session endpoints (Part B)
    # -----------------------------------------------------------------------

    @app.post("/api/entries/record")
    def entry_record(body: EntryRecordRequest):
        result = _btwin().record(
            content=body.content,
            topic=body.topic,
            project=body.project_id,
        )
        return result

    @app.post("/api/entries/search")
    def entry_search(body: EntrySearchRequest):
        btwin = _btwin()
        filters = {"record_type": body.record_type} if body.record_type else None
        if body.scope == "project" and body.project_id is not None:
            results = btwin.search(
                body.query,
                n_results=body.n_results,
                filters=filters,
                project=body.project_id,
            )
        else:
            results = btwin.search(
                body.query,
                n_results=body.n_results,
                filters=filters,
            )
        return {"results": results}

    @app.post("/api/entries/convo-record")
    def entry_convo_record(body: ConvoRecordRequest):
        result = _btwin().record_convo(
            content=body.content,
            requested_by_user=body.requested_by_user,
            topic=body.topic,
            project=body.project_id,
        )
        return result

    @app.post("/api/entries/import")
    def entry_import(body: EntryImportRequest):
        result = _btwin().import_entry(
            content=body.content,
            date=body.date,
            slug=body.slug,
            tags=body.tags,
            source_path=body.source_path,
            project=body.project_id,
        )
        return result

    @app.post("/api/sessions/start")
    def session_start(body: SessionStartRequest):
        result = _btwin().start_session(topic=body.topic)
        return result

    @app.post("/api/sessions/end")
    def session_end(body: SessionEndRequest):
        result = _btwin().end_session(
            summary=body.summary,
            slug=body.slug,
            project=body.project_id,
        )
        if result is None:
            return JSONResponse(status_code=200, content=None)
        return result

    @app.get("/api/sessions/status")
    def session_status():
        return _btwin().session_status()

    return app


def _resolve_runtime_openclaw_path(config: BTwinConfig) -> str | None:
    if config.runtime.mode == "standalone":
        return None

    env_path = os.environ.get("BTWIN_OPENCLAW_CONFIG_PATH")
    if env_path:
        return env_path

    if config.runtime.openclaw_config_path:
        return str(config.runtime.openclaw_config_path)

    return None


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
        runtime_mode=config.runtime.mode,
        extra_agents=extra_agents,
        openclaw_config_path=_resolve_runtime_openclaw_path(config),
        admin_token=os.environ.get("BTWIN_ADMIN_TOKEN"),
    )
