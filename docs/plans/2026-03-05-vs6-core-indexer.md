# VS6 Core Indexer & Document Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 문서 원본(entries)과 벡터 인덱스 사이 정합성을 코어 레벨에서 보장하는 인덱서 시스템(상태머신+manifest+운영 인터페이스)을 구현한다.

**Architecture:** 인덱서를 프레임워크 부가기능이 아닌 코어 컴포넌트로 도입한다. 문서 쓰기/수정/삭제는 모두 인덱서 상태(`pending/stale/deleted`)를 통해 벡터 반영 루프로 수렴되며, 검색은 항상 최신 manifest 기준으로 동작한다. 문서 타입 레지스트리와 스키마 검증을 코어에 배치해 프레임워크는 `doc_type + payload`만 전달하도록 단순화한다.

**Tech Stack:** Python 3.13, Pydantic v2, YAML manifest + atomic file write, ChromaDB, Typer CLI, FastAPI admin endpoints, pytest

---

## Implementation Constraints

- 이 계획은 **전용 worktree**에서 실행한다.
- DRY/YAGNI 유지: VS6 범위는 정합성 보장과 운영 제어(상태/동기화)까지.
- 모든 task는 TDD(실패 테스트 -> 최소 구현 -> 통과 -> 커밋)로 수행.
- commit은 task 단위로 잘게 유지.

---

### Task 1: Indexer 상태 모델/문서 계약 모델 추가

**Files:**
- Create: `src/btwin/core/indexer_models.py`
- Create: `tests/test_core/test_indexer_models.py`

**Step 1: Write the failing test**

```python
from pydantic import ValidationError
from btwin.core.indexer_models import IndexEntry


def test_index_entry_requires_core_fields():
    item = IndexEntry(
        doc_id="entries/convo/2026-03-05/convo-123.md",
        path="entries/convo/2026-03-05/convo-123.md",
        record_type="convo",
        checksum="sha256:abc",
        status="pending",
        doc_version=1,
    )
    assert item.status == "pending"


def test_index_entry_rejects_invalid_status():
    try:
        IndexEntry(
            doc_id="x", path="x", record_type="convo", checksum="sha256:x", status="bad", doc_version=1
        )
        assert False
    except ValidationError:
        assert True
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer_models.py -q`
Expected: FAIL with `ModuleNotFoundError: btwin.core.indexer_models`

**Step 3: Write minimal implementation**

```python
# src/btwin/core/indexer_models.py
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

IndexStatus = Literal["pending", "indexed", "stale", "failed", "deleted"]

class IndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    record_type: Literal["entry", "convo", "collab", "promoted"]
    checksum: str = Field(min_length=1)
    status: IndexStatus
    doc_version: int = Field(ge=1)
    error: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer_models.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/indexer_models.py tests/test_core/test_indexer_models.py
git commit -m "feat(indexer): add index entry status model"
```

---

### Task 2: Manifest 저장소(index_state) 추가

**Files:**
- Create: `src/btwin/core/indexer_manifest.py`
- Create: `tests/test_core/test_indexer_manifest.py`

**Step 1: Write the failing test**

```python
from btwin.core.indexer_manifest import IndexManifest


def test_manifest_upsert_and_load(tmp_path):
    manifest = IndexManifest(tmp_path / "index_manifest.yaml")
    manifest.upsert(
        doc_id="d1",
        path="entries/convo/2026-03-05/convo-1.md",
        record_type="convo",
        checksum="sha256:a",
        status="pending",
    )
    reloaded = IndexManifest(tmp_path / "index_manifest.yaml")
    item = reloaded.get("d1")
    assert item is not None
    assert item.status == "pending"
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer_manifest.py -q`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# IndexManifest with atomic save
# methods: get, upsert, mark_status, list_by_status, summary
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer_manifest.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/indexer_manifest.py tests/test_core/test_indexer_manifest.py
git commit -m "feat(indexer): add yaml manifest store with atomic write"
```

---

### Task 3: VectorStore 인덱서 보조 메서드(delete/get) 추가

**Files:**
- Modify: `src/btwin/core/vector.py`
- Modify: `tests/test_core/test_vector.py`

**Step 1: Write the failing test**

```python
from btwin.core.vector import VectorStore


def test_vector_delete_removes_document(tmp_path):
    vs = VectorStore(tmp_path / "index")
    vs.add("doc1", "hello", {"record_type": "entry"})
    assert vs.count() == 1
    vs.delete("doc1")
    assert vs.count() == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_vector.py::test_vector_delete_removes_document -q`
Expected: FAIL with `AttributeError: 'VectorStore' object has no attribute 'delete'`

**Step 3: Write minimal implementation**

```python
# vector.py add:
# def delete(self, doc_id: str) -> None
# def has(self, doc_id: str) -> bool
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_vector.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/vector.py tests/test_core/test_vector.py
git commit -m "feat(vector): add delete and existence helpers for indexer"
```

---

### Task 4: Core Indexer(refresh/reconcile/repair) 구현

**Files:**
- Create: `src/btwin/core/indexer.py`
- Create: `tests/test_core/test_indexer.py`
- Modify: `src/btwin/core/storage.py` (indexable 문서 iterator)

**Step 1: Write the failing test**

```python
from btwin.core.indexer import CoreIndexer


def test_refresh_indexes_pending_docs(tmp_path):
    idx = CoreIndexer(data_dir=tmp_path)
    idx.mark_pending(
        doc_id="entries/convo/2026-03-05/convo-1.md",
        path="entries/convo/2026-03-05/convo-1.md",
        record_type="convo",
        checksum="sha256:abc",
    )
    result = idx.refresh(limit=10)
    assert result["indexed"] == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer.py -q`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# CoreIndexer methods:
# mark_pending(...)
# refresh(limit)
# reconcile()
# status_summary()
# repair(doc_id)
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_indexer.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/indexer.py src/btwin/core/storage.py tests/test_core/test_indexer.py
git commit -m "feat(indexer): add refresh/reconcile/repair workflows"
```

---

### Task 5: BTwin 쓰기 경로를 인덱서 파이프라인으로 연결

**Files:**
- Modify: `src/btwin/core/btwin.py`
- Modify: `tests/test_core/test_btwin.py`

**Step 1: Write the failing test**

```python
from btwin.config import BTwinConfig
from btwin.core.btwin import BTwin


def test_record_marks_index_pending_and_refreshes(tmp_path):
    twin = BTwin(BTwinConfig(data_dir=tmp_path))
    out = twin.record("hello", topic="test")
    status = twin.indexer.status_summary()
    assert status["indexed"] >= 1
    assert out["path"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_btwin.py::test_record_marks_index_pending_and_refreshes -q`
Expected: FAIL (`BTwin` has no `indexer`)

**Step 3: Write minimal implementation**

```python
# BTwin.__init__ add self.indexer
# record/record_convo/import_entry paths:
# 1) write markdown
# 2) mark_pending
# 3) best-effort refresh(limit=1)
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_btwin.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/btwin.py tests/test_core/test_btwin.py
git commit -m "feat(core): route document writes through indexer pipeline"
```

---

### Task 6: CLI 인덱서 운영 명령 추가

**Files:**
- Modify: `src/btwin/cli/main.py`
- Create: `tests/test_cli/test_indexer_cli.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner
from btwin.cli.main import app


def test_indexer_status_command(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["indexer", "status"])
    assert res.exit_code == 0
    assert "indexed" in res.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_cli/test_indexer_cli.py -q`
Expected: FAIL (command not found)

**Step 3: Write minimal implementation**

```python
# add typer group: indexer
# commands:
# - btwin indexer status
# - btwin indexer refresh --limit
# - btwin indexer reconcile
# - btwin indexer repair --doc-id
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_cli/test_indexer_cli.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/cli/main.py tests/test_cli/test_indexer_cli.py
git commit -m "feat(cli): add indexer status/refresh/reconcile/repair commands"
```

---

### Task 7: API 운영 엔드포인트 추가(indexer status/refresh/reconcile)

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Create: `tests/test_api/test_indexer_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from btwin.api.collab_api import create_collab_app


def test_indexer_status_requires_admin_token(tmp_path):
    app = create_collab_app(data_dir=tmp_path, initial_agents={"main"}, admin_token="secret")
    client = TestClient(app)

    denied = client.get("/api/indexer/status")
    assert denied.status_code == 403

    ok = client.get("/api/indexer/status", headers={"X-Admin-Token": "secret"})
    assert ok.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_api/test_indexer_api.py -q`
Expected: FAIL (endpoint missing)

**Step 3: Write minimal implementation**

```python
# API endpoints:
# GET /api/indexer/status
# POST /api/indexer/refresh
# POST /api/indexer/reconcile
# admin-token protected
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_api/test_indexer_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/api/collab_api.py tests/test_api/test_indexer_api.py
git commit -m "feat(api): add admin indexer status/refresh/reconcile endpoints"
```

---

### Task 8: 문서 타입 레지스트리 + 규격 검증 경량 버전

**Files:**
- Create: `src/btwin/core/document_contracts.py`
- Create: `tests/test_core/test_document_contracts.py`
- Modify: `src/btwin/core/storage.py`

**Step 1: Write the failing test**

```python
from btwin.core.document_contracts import validate_document_contract


def test_collab_contract_requires_frontmatter_keys():
    ok, reason = validate_document_contract(
        record_type="collab",
        metadata={"recordId": "rec_1"},
    )
    assert ok is False
    assert "taskId" in reason
```

**Step 2: Run test to verify it fails**

Run: `uv run --python 3.13 pytest tests/test_core/test_document_contracts.py -q`
Expected: FAIL (module missing)

**Step 3: Write minimal implementation**

```python
# type별 required frontmatter map
# validate_document_contract(record_type, metadata) -> (bool, reason)
# storage write paths에서 1차 검증 호출
```

**Step 4: Run test to verify it passes**

Run: `uv run --python 3.13 pytest tests/test_core/test_document_contracts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/document_contracts.py src/btwin/core/storage.py tests/test_core/test_document_contracts.py
git commit -m "feat(core): add document contract registry and first-pass validation"
```

---

### Task 9: 통합 검증/문서화/운영 가이드

**Files:**
- Modify: `README.md`
- Create: `docs/indexer-operations.md`
- Modify: `docs/reports/2026-03-05-vs3-vs5-progress-report.md` (link out to VS6 if needed)

**Step 1: Write failing integration checklist tests**

```text
- stale 문서 refresh로 indexed 복구
- deleted 문서 vector 제거
- reconcile 후 manifest/vector/file 정합성 일치
```

**Step 2: Run full suite baseline**

Run: `uv run --python 3.13 pytest -q`
Expected: PASS (all existing + VS6 tests)

**Step 3: Write operations docs**

```markdown
# Indexer Operations
- btwin indexer status
- btwin indexer refresh --limit N
- btwin indexer reconcile
- btwin indexer repair --doc-id
- troubleshooting (failed 상태, checksum mismatch)
```

**Step 4: Re-run verification**

Run:
- `uv run --python 3.13 pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/indexer-operations.md docs/reports/2026-03-05-vs3-vs5-progress-report.md
git commit -m "docs(indexer): add VS6 operations guide and integration notes"
```

---

## Parallelization Plan

- Lane A (Core): Task 1,2,3,4,8
- Lane B (Interface): Task 6,7
- Lane C (Integration/Docs): Task 5,9 (A/B 완료 후)

병렬 조건:
1. `indexer_models.py`와 `indexer_manifest.py` 계약 먼저 확정
2. `VectorStore` 보조 메서드 merge 후 API/CLI 연결 시작
3. Interface task는 Core indexer service 생성 후 붙인다

---

## Execution Notes

- 필수 관련 스킬: `@test-driven-development`, `@verification-before-completion`, `@subagent-driven-development`
- 모든 명령은 프로젝트 루트(`b-twin/`)에서 실행
- Python 실행 통일:
  - `uv run --python 3.13 ...`

---

Plan complete and saved to `docs/plans/2026-03-05-vs6-core-indexer.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
