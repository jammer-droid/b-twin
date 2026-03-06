# Project Partitioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 중앙 저장소에서 프로젝트별로 데이터를 분리 저장/검색하는 마스터/프록시 구조를 구현한다.

**Architecture:** Storage 경로에 project 레벨을 추가하고, 인덱서/벡터에 project 메타데이터를 추가한다. HTTP API에 project 파라미터를 추가하고, 경량 MCP 프록시를 만들어 프로젝트 컨텍스트를 서버 레벨에서 강제한다.

**Tech Stack:** Python, FastAPI, Pydantic, httpx, mcp[cli], pytest

**Design doc:** `docs/plans/2026-03-06-project-partitioning-design.md`

---

### Task 1: Storage 경로에 project 레벨 추가

**Files:**
- Modify: `src/btwin/core/storage.py`
- Test: `tests/test_core/test_project_storage.py`
- Reference: `src/btwin/core/storage.py` (현재 save_entry, list_entries, save_convo_record, list_indexable_documents)

**Step 1: Write failing tests**

Cover:
- `save_entry(entry, project="myproj")` → `entries/myproj/{date}/{slug}.md` 경로에 저장
- `save_entry(entry, project=None)` → `entries/_global/{date}/{slug}.md` 폴백
- `list_entries(project="myproj")` → 해당 프로젝트 엔트리만 반환
- `list_entries(project=None)` → 전체 프로젝트 엔트리 반환
- `save_convo_record(..., project="myproj")` → `entries/myproj/convo/{date}/{slug}.md`
- `save_collab_record(record, project="myproj")` → `entries/myproj/collab/{date}/{slug}.md`
- `list_indexable_documents(project="myproj")` → 해당 프로젝트 문서만 반환, 메타데이터에 `project` 포함
- 프론트매터에 `project` 필드 포함 확인

Run: `uv run pytest -q tests/test_core/test_project_storage.py`
Expected: FAIL because project parameter not supported yet.

**Step 2: Implement Storage project support**

변경 사항:
- `save_entry(self, entry, *, project: str | None = None)` — project가 None이면 `_global`, 있으면 해당 이름으로 경로 생성. 프론트매터에 `project` 필드 추가.
- `list_entries(self, *, project: str | None = None)` — project 지정 시 `entries/{project}/` 하위만 순회. None이면 모든 프로젝트의 date 폴더 순회.
- `save_convo_record(self, ..., project: str | None = None)` — `entries/{project}/convo/{date}/` 경로
- `save_collab_record(self, record, *, project: str | None = None)` — `entries/{project}/collab/{date}/` 경로
- `list_indexable_documents(self, *, project: str | None = None)` — 반환 dict에 `"project"` 키 추가
- `_FRAMEWORK_DIRS`에 더 이상 의존하지 않고 프로젝트 디렉토리 구조로 구분

주의: 기존 테스트가 project=None (즉 `_global`) 동작으로 깨지지 않도록 하위호환 유지.

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_core/test_project_storage.py`
Expected: PASS

**Step 4: Run existing tests to check backward compat**

Run: `uv run pytest -q`
Expected: PASS (기존 테스트 깨지지 않음)

**Step 5: Commit**

```bash
git add src/btwin/core/storage.py tests/test_core/test_project_storage.py
git commit -m "feat(storage): add project-level path partitioning"
```

---

### Task 2: Indexer/Vector에 project 메타데이터 추가

**Files:**
- Modify: `src/btwin/core/indexer_models.py`
- Modify: `src/btwin/core/indexer.py`
- Modify: `src/btwin/core/vector.py` (벡터 메타데이터에 project 추가하는 부분은 indexer.py의 refresh에서 처리)
- Test: `tests/test_core/test_project_indexer.py`
- Reference: `src/btwin/core/indexer_models.py` (IndexEntry 모델)

**Step 1: Write failing tests**

Cover:
- `IndexEntry`에 `project: str | None = None` 필드 존재
- `mark_pending(..., project="myproj")` → 매니페스트에 project 저장
- `refresh()` 시 벡터 메타데이터에 `project` 포함
- `reconcile()` 시 storage에서 가져온 project 정보 유지
- `status_summary(project="myproj")` → 해당 프로젝트만 집계
- `failure_queue(project="myproj")` → 해당 프로젝트만 필터

Run: `uv run pytest -q tests/test_core/test_project_indexer.py`
Expected: FAIL

**Step 2: Implement indexer project support**

변경 사항:
- `indexer_models.py`: `IndexEntry`에 `project: str | None = None` 필드 추가
- `indexer.py`:
  - `mark_pending(...)` — `project` 파라미터 추가, IndexEntry에 저장
  - `refresh()` — 벡터 add 시 metadata에 `"project": item.project or "_global"` 추가
  - `reconcile()` — `list_indexable_documents()`에서 받은 project 정보를 mark_pending에 전달
  - `status_summary(project=None)` — project 필터 옵션 추가
  - `failure_queue(limit, project=None)` — project 필터 옵션 추가

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_core/test_project_indexer.py`
Expected: PASS

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/indexer_models.py src/btwin/core/indexer.py tests/test_core/test_project_indexer.py
git commit -m "feat(indexer): add project metadata to manifest and vector index"
```

---

### Task 3: BTwin core에 project 전달 경로 연결

**Files:**
- Modify: `src/btwin/core/btwin.py`
- Test: `tests/test_core/test_project_btwin.py`
- Reference: `src/btwin/core/btwin.py` (record, search, record_convo, import_entry)

**Step 1: Write failing tests**

Cover:
- `BTwin.record(content, project="myproj")` → storage에 project 전달
- `BTwin.record_convo(content, project="myproj")` → storage에 project 전달
- `BTwin.import_entry(..., project="myproj")` → storage에 project 전달
- `BTwin.search(query, project="myproj")` → vector search에 `{"project": "myproj"}` 필터 전달
- `BTwin.search(query, project=None)` → 필터 없이 전체 검색
- 인덱싱 시 project 메타데이터 전달 확인

Run: `uv run pytest -q tests/test_core/test_project_btwin.py`
Expected: FAIL

**Step 2: Implement BTwin project passthrough**

변경 사항:
- `record(self, content, topic=None, *, project: str | None = None)` — storage.save_entry에 project 전달, _index_file에 project 전달
- `record_convo(self, content, ..., project: str | None = None)` — storage.save_convo_record에 project 전달
- `import_entry(self, ..., project: str | None = None)` — storage.save_entry에 project 전달
- `search(self, query, ..., project: str | None = None)` — project 있으면 filters에 `{"project": project}` 병합
- `_index_file(self, path, record_type, *, project: str | None = None)` — indexer.mark_pending에 project 전달

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_core/test_project_btwin.py`
Expected: PASS

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/core/btwin.py tests/test_core/test_project_btwin.py
git commit -m "feat(core): wire project parameter through BTwin record and search"
```

---

### Task 4: HTTP API에 project 파라미터 추가

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Test: `tests/test_api/test_project_api.py`
- Reference: `src/btwin/api/collab_api.py` (기존 엔드포인트 패턴)

**Step 1: Write failing tests**

Cover:
- `POST /api/collab/records` — body에 `projectId` 포함 시 해당 프로젝트에 저장
- `GET /api/collab/records?projectId=myproj` — 해당 프로젝트만 필터
- `POST /api/collab/handoff` — body에 `projectId` 포함
- `GET /api/ops/dashboard?projectId=myproj` — 프로젝트별 대시보드
- `GET /api/indexer/status?projectId=myproj` — 프로젝트별 인덱서 상태
- `POST /api/entries/record` 추가 — project 파라미터로 기록 (프록시가 호출할 엔드포인트)
- `POST /api/entries/search` 추가 — project 파라미터로 검색 (프록시가 호출할 엔드포인트)

Run: `uv run pytest -q tests/test_api/test_project_api.py`
Expected: FAIL

**Step 2: Implement API project support**

변경 사항:
- 요청 모델에 `project_id: str | None = Field(default=None, alias="projectId")` 추가
- 리스트/상태 엔드포인트에 `projectId` 쿼리 파라미터 추가
- 프록시용 엔드포인트 추가:
  - `POST /api/entries/record` — `{"content": "...", "topic": "...", "projectId": "..."}` → btwin.record 호출
  - `POST /api/entries/search` — `{"query": "...", "nResults": 5, "projectId": "...", "scope": "project|all"}` → btwin.search 호출
  - `POST /api/entries/convo-record` — btwin.record_convo 호출
  - `POST /api/entries/import` — btwin.import_entry 호출
  - `POST /api/sessions/start` — btwin.start_session 호출
  - `POST /api/sessions/end` — btwin.end_session 호출
  - `GET /api/sessions/status` — btwin.session_status 호출

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_api/test_project_api.py`
Expected: PASS

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/api/collab_api.py tests/test_api/test_project_api.py
git commit -m "feat(api): add project parameter to collab and entry endpoints"
```

---

### Task 5: MCP 프록시 서버 구현

**Files:**
- Create: `src/btwin/mcp/proxy.py`
- Test: `tests/test_mcp/test_proxy.py`
- Reference: `src/btwin/mcp/server.py` (기존 MCP 서버 도구 정의 참고)

**Step 1: Write failing tests**

Cover:
- 프록시가 `--project` 인자를 받아 저장
- `btwin_record` 호출 시 HTTP POST `/api/entries/record`에 `projectId` 포함
- `btwin_search` 호출 시 HTTP POST `/api/entries/search`에 `projectId` 포함
- `btwin_convo_record` 호출 시 `projectId` 포함
- `btwin_import_entry` 호출 시 `projectId` 포함
- `btwin_start_session`, `btwin_end_session`, `btwin_session_status` 전달
- `btwin_search`에 `scope="all"` 옵션 시 projectId 없이 전체 검색
- backend URL 미응답 시 에러 메시지

Run: `uv run pytest -q tests/test_mcp/test_proxy.py`
Expected: FAIL

**Step 2: Implement MCP proxy**

`src/btwin/mcp/proxy.py`:
- `httpx` + `mcp[cli]`만 import. ChromaDB, indexer, storage 등 무거운 모듈 import 없음.
- 시작 시 `--project`와 `--backend` 인자 파싱
- 기존 MCP 서버와 동일한 도구 이름/시그니처 노출 (LLM 입장에서 차이 없음)
- 각 도구 호출 시 HTTP 요청에 `projectId` 자동 주입
- `btwin_search`에 `scope: str = "project"` 파라미터 추가 ("project" 또는 "all")

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_mcp/test_proxy.py`
Expected: PASS

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/mcp/proxy.py tests/test_mcp/test_proxy.py
git commit -m "feat(mcp): add lightweight project-aware proxy server"
```

---

### Task 6: CLI — init 명령 및 mcp-proxy 명령 추가

**Files:**
- Modify: `src/btwin/cli/main.py`
- Modify: `install.sh`
- Test: `tests/test_cli/test_project_cli.py`

**Step 1: Write failing tests**

Cover:
- `btwin init` — git repo명에서 프로젝트명 자동 추출, `.mcp.json` 생성
- `btwin init my-project` — 명시적 이름으로 `.mcp.json` 생성
- `.mcp.json` 내용에 `proxy.sh --project {name}` 포함 확인
- `btwin mcp-proxy --project x --backend http://localhost:8787` — 프록시 시작 (import 확인 수준)
- `btwin init` 이미 `.mcp.json` 존재 시 덮어쓰기 전 확인

Run: `uv run pytest -q tests/test_cli/test_project_cli.py`
Expected: FAIL

**Step 2: Implement CLI commands**

- `btwin init [project_name]`:
  - project_name 미지정 시: git remote/디렉토리명에서 추출
  - `.mcp.json` 생성: `{"mcpServers": {"btwin": {"command": "~/.btwin/proxy.sh", "args": ["--project", name]}}}`
  - 이미 존재 시 확인 프롬프트

- `btwin mcp-proxy --project NAME --backend URL`:
  - `src/btwin/mcp/proxy.py`의 main 호출

- `install.sh` 수정:
  - `~/.btwin/proxy.sh` 생성 추가: `btwin mcp-proxy "$@"` 래퍼
  - 설치 완료 메시지에 프로젝트 세팅 안내 추가

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_cli/test_project_cli.py`
Expected: PASS

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/btwin/cli/main.py install.sh tests/test_cli/test_project_cli.py
git commit -m "feat(cli): add btwin init and mcp-proxy commands"
```

---

### Task 7: 기존 데이터 마이그레이션 스크립트

**Files:**
- Create: `scripts/migrate_to_project_layout.py`
- Test: `tests/test_scripts/test_migration.py`

**Step 1: Write failing tests**

Cover:
- `entries/{date}/{slug}.md` → `entries/_global/{date}/{slug}.md` 이동
- `entries/convo/{date}/` → `entries/_global/convo/{date}/` 이동
- `entries/collab/{date}/` → `entries/_global/collab/{date}/` 이동
- `entries/global/promoted/` → `entries/_global/global/promoted/` 이동
- 프론트매터에 `project: _global` 추가
- 이동 후 원본 디렉토리 정리
- 빈 디렉토리 제거
- 이미 마이그레이션된 경우 (entries/_global/ 존재) 스킵
- dry-run 모드 지원

Run: `uv run pytest -q tests/test_scripts/test_migration.py`
Expected: FAIL

**Step 2: Implement migration script**

`scripts/migrate_to_project_layout.py`:
- `--data-dir` 인자 (기본: `~/.btwin`)
- `--dry-run` 플래그
- 기존 date 폴더 (`YYYY-MM-DD`) 와 framework 폴더 (`convo`, `collab`, `global`)를 `_global/` 하위로 이동
- 각 파일의 프론트매터에 `project: _global` 추가
- 이동 완료 후 `btwin indexer reconcile` 안내 출력

**Step 3: Run tests**

Run: `uv run pytest -q tests/test_scripts/test_migration.py`
Expected: PASS

**Step 4: Commit**

```bash
git add scripts/migrate_to_project_layout.py tests/test_scripts/test_migration.py
git commit -m "feat(scripts): add migration script for project layout"
```

---

### Task 8: 문서 업데이트 및 전체 검증

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Create: `docs/reports/2026-03-06-project-partitioning-test-guide.md`

**Step 1: Update README.md**

추가/수정할 섹션:
- **프로젝트 구조**: 저장 경로 레이아웃 다이어그램
- **설치/세팅**: `install.sh` → `btwin init` 흐름
- **MCP Tools**: project 동작 설명 (서버 바인딩, 프록시)
- **OpenClaw 연동**: 봇 워크스페이스에 proxy.sh 설정 방법
- **마이그레이션**: 기존 데이터 마이그레이션 가이드

**Step 2: Update docs/runbook.md**

추가할 섹션:
- 프로젝트별 인덱서 상태 확인
- 프로젝트 간 데이터 검색
- 마이그레이션 후 reconcile 절차

**Step 3: Create test guide**

`docs/reports/2026-03-06-project-partitioning-test-guide.md`:
- 프로젝트별 저장/검색 수동 테스트 절차
- 마이그레이션 검증 체크리스트
- MCP 프록시 연결 테스트

**Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/runbook.md docs/reports/2026-03-06-project-partitioning-test-guide.md
git commit -m "docs: add project partitioning usage guide and runbook updates"
```

---
