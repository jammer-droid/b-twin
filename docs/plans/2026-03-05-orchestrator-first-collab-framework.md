# Orchestrator-First Collab Framework + Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** B-TWIN을 오케스트레이터 우선 협업 프레임워크로 확장하고, collab/convo 분리 기록 + 승격 큐 + 시각화 대시보드를 Vertical Slice 방식으로 출시한다.

**Architecture:** OpenClaw 오케스트레이터가 1차 하드 게이트(완료/핸드오프 전 필수 collab 레코드 검사)를 담당하고, B-TWIN 코어는 상태 저장/승격 큐/조회 API를 제공한다. Dashboard는 같은 데이터 계약을 사용해 진행 상태/승격 상태를 시각화한다. 일반 작업 상태(collab)와 승격 상태(promotion)는 별도 상태머신으로 분리한다.

**Tech Stack:** Python 3.13+, FastMCP, Typer, YAML frontmatter, ChromaDB(검색), FastAPI(+Uvicorn) for dashboard API, React/Next.js dashboard UI (existing dashboard spec aligned)

---

## Global Rules (모든 VS 공통)

- 권한 정책
  - collab draft read: 모든 에이전트 허용
  - global 승격 write: Vincent만 허용
- 상태 정책
  - collab: `draft -> handed_off -> completed`
  - promotion queue: `proposed -> approved -> queued -> promoted`
- 강제 정책
  - collab 하드 게이트 트리거: `handoff`, `complete` 둘 다
- convo 정책
  - 기본 소프트, 사용자 명시 요청 시 강제 기록

---

## Vertical Slice 1 (VS1): Collab 기록 계약 + 하드 게이트 + 최소 시각화

### Task 1: Collab 스키마/상태 모델 추가

**Files:**
- Create: `src/btwin/core/collab_models.py`
- Modify: `src/btwin/core/models.py`
- Test: `tests/test_core/test_collab_models.py`

**Step 1: Write the failing test**

```python
# tests/test_core/test_collab_models.py
from btwin.core.collab_models import CollabRecord

def test_collab_record_requires_schema_b_fields():
    record = CollabRecord(
        task_id="task-1",
        record_type="collab",
        summary="요약",
        evidence=["pytest pass"],
        next_action=["handoff to codex-code"],
        status="draft",
        author_agent="research-bot",
        created_at="2026-03-05T15:00:00+09:00",
    )
    assert record.record_type == "collab"
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_collab_models.py -v`
Expected: FAIL with `ModuleNotFoundError` for `btwin.core.collab_models`

**Step 3: Write minimal implementation**

```python
# src/btwin/core/collab_models.py
from dataclasses import dataclass
from typing import Literal

CollabStatus = Literal["draft", "handed_off", "completed"]

@dataclass
class CollabRecord:
    task_id: str
    record_type: Literal["collab"]
    summary: str
    evidence: list[str]
    next_action: list[str]
    status: CollabStatus
    author_agent: str
    created_at: str
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_collab_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/collab_models.py src/btwin/core/models.py tests/test_core/test_collab_models.py
git commit -m "feat(core): add collab record schema and status model"
```

---

### Task 2: Collab 저장소(물리 분리 + frontmatter) 구현

**Files:**
- Modify: `src/btwin/core/storage.py`
- Create: `tests/test_core/test_collab_storage.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from btwin.core.storage import Storage


def test_save_collab_record_to_collab_directory(tmp_path: Path):
    storage = Storage(tmp_path)
    path = storage.save_collab_record(
        task_id="task-1",
        summary="요약",
        evidence=["proof"],
        next_action=["next"],
        status="draft",
        author_agent="codex-code",
        created_at="2026-03-05T15:00:00+09:00",
    )
    assert "entries/collab" in str(path)
    assert path.read_text().startswith("---")
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_collab_storage.py -v`
Expected: FAIL with `AttributeError: 'Storage' object has no attribute 'save_collab_record'`

**Step 3: Write minimal implementation**

```python
# storage.py (추가)
def save_collab_record(...):
    # entries/collab/YYYY-MM-DD/<task_id>-<status>.md 저장
    # frontmatter에 B 스키마 필수 필드 작성
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_collab_storage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/storage.py tests/test_core/test_collab_storage.py
git commit -m "feat(storage): add collab record persistence with segregated directory"
```

---

### Task 3: 하드 게이트(complete/handoff) 규칙 엔진 추가

**Files:**
- Create: `src/btwin/core/gate.py`
- Create: `tests/test_core/test_gate.py`

**Step 1: Write the failing test**

```python
from btwin.core.gate import validate_handoff_gate


def test_handoff_requires_collab_record_id():
    ok, reason = validate_handoff_gate(record_id=None, status="draft")
    assert ok is False
    assert "record" in reason.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_gate.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/btwin/core/gate.py
def validate_handoff_gate(record_id: str | None, status: str):
    if not record_id:
        return False, "collab record required before handoff"
    if status not in {"draft", "handed_off", "completed"}:
        return False, "invalid status"
    return True, "ok"

def validate_complete_gate(record_id: str | None, status: str):
    if not record_id:
        return False, "collab record required before complete"
    if status not in {"handed_off", "completed"}:
        return False, "complete requires handed_off/completed state"
    return True, "ok"
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_gate.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/gate.py tests/test_core/test_gate.py
git commit -m "feat(core): add hard gate validators for handoff and complete"
```

---

### Task 4: MCP 도구 추가 (collab 기록/핸드오프/완료)

**Files:**
- Modify: `src/btwin/mcp/server.py`
- Modify: `tests/test_mcp/test_server.py`

**Step 1: Write the failing test**

```python
def test_btwin_collab_handoff_requires_record(mock_get_twin):
    result = btwin_collab_handoff(task_id="task-1", record_id=None, to_agent="codex-code")
    assert "required" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_mcp/test_server.py::test_btwin_collab_handoff_requires_record -v`
Expected: FAIL because tool function not found

**Step 3: Write minimal implementation**

```python
@mcp.tool()
def btwin_collab_record(...): ...

@mcp.tool()
def btwin_collab_handoff(task_id: str, record_id: str | None, to_agent: str) -> str:
    ok, reason = validate_handoff_gate(record_id=record_id, status="draft")
    if not ok:
        return f"Gate rejected: {reason}"
    return f"handoff accepted: {task_id} -> {to_agent}"
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_mcp/test_server.py -v`
Expected: PASS (기존 테스트 포함)

**Step 5: Commit**

```bash
git add src/btwin/mcp/server.py tests/test_mcp/test_server.py
git commit -m "feat(mcp): add collab tools with hard gate checks"
```

---

### Task 5: Dashboard 최소 뷰 (Collab List/Status)

**Files:**
- Create: `dashboard/web/src/pages/collab.tsx`
- Create: `dashboard/web/src/lib/api/collab.ts`
- Test: `dashboard/web/src/pages/collab.test.tsx`

**Step 1: Write failing UI test**

```tsx
it("renders collab records with status badges", async () => {
  render(<CollabPage />)
  expect(await screen.findByText("task-1")).toBeInTheDocument()
  expect(screen.getByText("completed")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `npm test -- collab.test.tsx`
Expected: FAIL (page/module missing)

**Step 3: Write minimal page implementation**

```tsx
export default function CollabPage() {
  // fetch /api/collab/records
  // render table(taskId, status, authorAgent, createdAt)
}
```

**Step 4: Run test to verify it passes**

Run: `npm test -- collab.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/web/src/pages/collab.tsx dashboard/web/src/lib/api/collab.ts dashboard/web/src/pages/collab.test.tsx
git commit -m "feat(dashboard): add collab status list page"
```

---

## Vertical Slice 2 (VS2): Promotion Proposal + Vincent Approval UI

### Task 6: Promotion queue 모델/저장소 추가

**Files:**
- Create: `src/btwin/core/promotion_models.py`
- Create: `src/btwin/core/promotion_store.py`
- Test: `tests/test_core/test_promotion_store.py`

**Step 1: Write failing test**

```python
def test_enqueue_promotion_sets_proposed_status(tmp_path):
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec-1", proposed_by="codex-code")
    assert item.status == "proposed"
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_promotion_store.py -v`
Expected: FAIL (module missing)

**Step 3: Write minimal implementation**

```python
# status: proposed|approved|queued|promoted
# YAML 기반 큐 저장/로드/enqueue/approve 제공
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_promotion_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/promotion_models.py src/btwin/core/promotion_store.py tests/test_core/test_promotion_store.py
git commit -m "feat(core): add promotion queue store and status model"
```

---

### Task 7: Vincent 전용 승인 게이트 구현

**Files:**
- Modify: `src/btwin/core/gate.py`
- Modify: `src/btwin/mcp/server.py`
- Test: `tests/test_core/test_gate.py`

**Step 1: Write failing test**

```python
def test_only_vincent_can_approve_promotion():
    ok, _ = validate_promotion_approval(actor_agent="research-bot")
    assert ok is False
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_gate.py::test_only_vincent_can_approve_promotion -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def validate_promotion_approval(actor_agent: str):
    if actor_agent != "main":
        return False, "only Vincent(main) can approve promotion"
    return True, "ok"
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_gate.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/gate.py src/btwin/mcp/server.py tests/test_core/test_gate.py
git commit -m "feat(gate): enforce Vincent-only promotion approval"
```

---

### Task 8: Approval UI + API 연결

**Files:**
- Create: `dashboard/web/src/pages/promotions.tsx`
- Create: `dashboard/web/src/pages/promotions.test.tsx`
- Modify: `docs/dashboard-implementation-spec.md`

**Step 1: Write failing UI test**

```tsx
it("shows proposed promotions and approve button", async () => {
  render(<PromotionsPage />)
  expect(await screen.findByText("proposed")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `npm test -- promotions.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

```tsx
// proposed 목록 + approve action
// approve 호출 시 /api/promotions/{id}/approve
```

**Step 4: Run test to verify it passes**

Run: `npm test -- promotions.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/web/src/pages/promotions.tsx dashboard/web/src/pages/promotions.test.tsx docs/dashboard-implementation-spec.md
git commit -m "feat(dashboard): add promotion proposal approval page"
```

---

## Vertical Slice 3 (VS3): 배치 승격 + Global 반영 시각화

### Task 9: 배치 승격 워커 구현

**Files:**
- Create: `src/btwin/core/promotion_worker.py`
- Create: `tests/test_core/test_promotion_worker.py`

**Step 1: Write failing test**

```python
def test_worker_promotes_approved_items_to_global(tmp_path):
    # approved item -> promoted + global entry 생성
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_promotion_worker.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# approved -> queued -> promoted 전이
# source_record_id 기반 global 문서 생성
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_promotion_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/promotion_worker.py tests/test_core/test_promotion_worker.py
git commit -m "feat(core): add batch promotion worker"
```

---

### Task 10: 사용자 지정 배치 스케줄 설정 추가 (기본 하루 1~2회)

**Files:**
- Modify: `src/btwin/config.py`
- Modify: `src/btwin/cli/main.py`
- Create: `tests/test_core/test_config_promotion.py`

**Step 1: Write failing test**

```python
def test_default_promotion_schedule_is_daily_twice():
    cfg = BTwinConfig()
    assert cfg.promotion.schedule == "0 9,21 * * *"
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_config_promotion.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# config에 promotion.schedule, promotion.enabled 추가
# CLI: btwin promotion run / btwin promotion schedule --set
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_config_promotion.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/config.py src/btwin/cli/main.py tests/test_core/test_config_promotion.py
git commit -m "feat(config): add configurable promotion batch schedule"
```

---

### Task 11: Promoted 히스토리 시각화

**Files:**
- Create: `dashboard/web/src/pages/promoted.tsx`
- Create: `dashboard/web/src/pages/promoted.test.tsx`

**Step 1: Write failing UI test**

```tsx
it("renders promoted records with source reference", async () => {
  render(<PromotedPage />)
  expect(await screen.findByText(/source record/i)).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `npm test -- promoted.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

```tsx
// promoted 목록 + sourceRecordId 링크 + promotedAt 표시
```

**Step 4: Run test to verify it passes**

Run: `npm test -- promoted.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/web/src/pages/promoted.tsx dashboard/web/src/pages/promoted.test.tsx
git commit -m "feat(dashboard): add promoted history page"
```

---

## Vertical Slice 4 (VS4): Convo 명시 기록 + 조회 분리

### Task 12: Convo 명시 기록 API/도구 추가

**Files:**
- Modify: `src/btwin/mcp/server.py`
- Modify: `src/btwin/core/storage.py`
- Create: `tests/test_mcp/test_convo_record.py`

**Step 1: Write failing test**

```python
def test_explicit_convo_record_saves_under_convo_dir(...):
    result = btwin_convo_record(content="기억해줘", requested_by_user=True)
    assert "entries/convo" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_mcp/test_convo_record.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
@mcp.tool()
def btwin_convo_record(content: str, requested_by_user: bool = False):
    # requested_by_user=True 이면 강제 저장
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_mcp/test_convo_record.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/mcp/server.py src/btwin/core/storage.py tests/test_mcp/test_convo_record.py
git commit -m "feat(mcp): add explicit convo recording flow"
```

---

### Task 13: Collab/Convo 필터 검색 추가

**Files:**
- Modify: `src/btwin/core/vector.py`
- Modify: `src/btwin/core/btwin.py`
- Create: `tests/test_core/test_vector_filters.py`

**Step 1: Write failing test**

```python
def test_vector_search_filters_by_record_type():
    # record_type=collab 필터 시 collab만 반환
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_vector_filters.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# vector search 인자에 metadata_filters 추가
# btwin.search(query, filters={"record_type": "collab"})
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_vector_filters.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/vector.py src/btwin/core/btwin.py tests/test_core/test_vector_filters.py
git commit -m "feat(search): add record-type metadata filtering"
```

---

### Task 14: Dashboard 필터 통합(convo/collab)

**Files:**
- Modify: `dashboard/web/src/pages/entries.tsx`
- Create: `dashboard/web/src/components/RecordTypeFilter.tsx`
- Test: `dashboard/web/src/pages/entries.filter.test.tsx`

**Step 1: Write failing UI test**

```tsx
it("filters list by selected record type", async () => {
  render(<EntriesPage />)
  await user.click(screen.getByLabelText("collab"))
  expect(screen.queryByText("convo item")).not.toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `npm test -- entries.filter.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

```tsx
// recordType 필터 UI + query param 전달
```

**Step 4: Run test to verify it passes**

Run: `npm test -- entries.filter.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add dashboard/web/src/pages/entries.tsx dashboard/web/src/components/RecordTypeFilter.tsx dashboard/web/src/pages/entries.filter.test.tsx
git commit -m "feat(dashboard): add convo/collab filter controls"
```

---

## Vertical Slice 5 (VS5): 운영 안정화 + 병렬 실행 전략

### Task 15: 운영 메트릭/감사 로그 추가

**Files:**
- Create: `src/btwin/core/audit.py`
- Modify: `src/btwin/mcp/server.py`
- Test: `tests/test_core/test_audit.py`

**Step 1: Write failing test**

```python
def test_gate_rejection_is_logged_with_reason(tmp_path):
    ...
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_audit.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# gate reject, promotion actions를 JSONL 감사 로그로 저장
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_audit.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/audit.py src/btwin/mcp/server.py tests/test_core/test_audit.py
git commit -m "feat(observability): add audit logging for gate and promotion events"
```

---

### Task 16: 전체 회귀 테스트 + 문서화

**Files:**
- Modify: `README.md`
- Modify: `docs/dashboard-implementation-spec.md`
- Create: `docs/collab-framework-ops.md`

**Step 1: Write/extend failing integration tests list**

```text
- collab gate reject/accept
- promotion queue lifecycle
- convo explicit save
- dashboard filtering
```

**Step 2: Run full test suite baseline**

Run: `uv run --python 3.13 pytest -v`
Expected: 모든 신규 테스트 포함 PASS

**Step 3: Update docs with runbook**

```markdown
# Collab Framework Ops
- gate failure triage
- promotion batch manual run
- Vincent approval flow
```

**Step 4: Re-run verification**

Run:
- `uv run --python 3.13 pytest -v`
- `npm test`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/dashboard-implementation-spec.md docs/collab-framework-ops.md
git commit -m "docs: add collab framework and dashboard operations guide"
```

---

## Parallelization Plan (요청 반영)

- **VS1 이후부터 백엔드/UI 병렬 가능**
  - Lane A (Backend): Task 6,7,9,10,12,13,15
  - Lane B (UI): Task 8,11,14
- 병렬 조건
  1. 공통 계약 고정: `collab_models.py`, promotion status enum, API response schema
  2. 계약 변경 시 PR당 1회만 배치 반영
  3. Merge 순서: Backend contract PR -> UI binding PR

---

## Execution Notes

- 필수 작업 습관:
  - @test-driven-development
  - @verification-before-completion
  - 작은 커밋 유지(태스크 단위)
- Python 실행 통일:
  - `uv run --python 3.13 ...`

---

Plan complete and saved to `docs/plans/2026-03-05-orchestrator-first-collab-framework.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
