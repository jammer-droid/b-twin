---
doc_version: 1
last_updated: 2026-03-07
status: draft
reviews:
  - docs/plans/2026-03-07-orchestration-engine-implementation-plan.md
---

# Orchestration Engine Implementation Plan — Review

## Overall Assessment

구현 계획서는 설계 논의 결과를 잘 반영하고 있고, 전체적으로 실행 가능한 수준입니다.

12개 태스크의 순서가 자연스러운 의존성 체인을 따르고 있고 (models → storage → engine → gate → normalization → dispatch → completion → context → watchdog → MCP → docs), TDD 접근(실패 테스트 → 구현 → 통과)이 일관성 있게 적용되어 있습니다.

아래는 실행 전에 보완하면 좋을 포인트들입니다.

---

## 보완 권장 사항

### 1. Workflow CRUD API 태스크가 빠져 있음

기존 MVP 계획(Task 4)에 있었던 워크플로 CRUD 엔드포인트 구현이 새 계획에서 독립 태스크로 없습니다:
- `POST /api/workflows/epics` — 워크플로 생성
- `GET /api/workflows/epics` — 워크플로 목록
- `POST /api/workflows/tasks` — 태스크 생성
- `GET /api/workflows/tasks` — 태스크 목록
- `GET /api/workflows/runs` — 실행 이력 조회

Task 8은 completion API만, Task 10은 recovery API만 다룹니다. Task 11은 MCP 툴이지 HTTP API가 아닙니다.

**권장:** Task 7과 Task 8 사이에 "Workflow CRUD API scaffold" 태스크를 추가하거나, Task 8의 범위를 CRUD + completion으로 확장해야 합니다. 이 API 없이는 워크플로를 생성할 방법이 MCP 툴(Task 11)뿐인데, MCP 툴은 내부적으로 API를 호출하는 proxy 구조이므로 HTTP API가 먼저 있어야 합니다.

---

### 2. 인덱서 호환성 확인이 누락됨

기존 MVP 계획(Task 3)에 있었던 "Indexer compatibility check for workflow docs"가 새 계획에 없습니다.

워크플로 문서가 기존 인덱서에서 정상 색인되는지 확인해야 합니다:
- `record_type` 필터링 가능 여부
- 체크섬/doc_version 동작
- 매니페스트 reconciliation 시 워크플로 네임스페이스 처리

**권장:** Task 3(storage) 완료 후, Task 4 전에 인덱서 호환성 검증 스텝을 추가하거나 Task 3에 통합.

---

### 3. workflow_engine.py와 workflow_gate.py의 경계가 모호함

Task 4에서 `workflow_engine.py`를 생성하고, Task 5에서 `workflow_gate.py`를 수정합니다. 두 모듈 모두 Layer 2(Workflow Engine)에 속하는데, 책임 분리가 명시적이지 않습니다.

현재 암묵적 분리:
- `workflow_engine.py` = 상태 재구축(rebuild) + 불일치 감지
- `workflow_gate.py` = 전이 규칙 + next-step 계산

**권장:** Task 4 또는 Task 5의 설명에 두 모듈의 책임 경계를 명시.

예시:
- `workflow_gate.py`: 순수 전이 함수 — "현재 상태 + 이벤트 → 다음 상태" 계산만
- `workflow_engine.py`: 상태 조회, 재구축, 불일치 감지, gate 결과를 materialized state에 반영하는 조율자

---

### 4. 감사(audit) 통합이 명시적으로 빠져 있음

설계 문서에서 모든 전이에 감사 로그를 남기기로 했지만, 구현 계획의 어떤 태스크에도 "audit entry 작성" 테스트가 명시되어 있지 않습니다.

기존 `audit.py` 모듈이 있고 JSONL 로그 인프라도 있으므로, 전이/완료/리뷰/복구 시점마다 감사 엔트리가 기록되는지 검증해야 합니다.

**권장:** Task 5(transition gate) 또는 Task 8(completion handler)의 테스트 커버리지에 "audit entry가 기록됨을 검증" 항목 추가.

---

### 5. collab_api.py 비대화 리스크

Task 8과 Task 10 모두 `collab_api.py`를 수정합니다. 기존 TODO(B6)에서 이미 "collab_api.py가 dumping ground가 되는 것 방지"를 언급했습니다.

워크플로 CRUD + completion + recovery 라우트까지 더하면 이 파일이 상당히 커질 수 있습니다.

**권장:** Task 8 시점에서 워크플로 라우트를 별도 파일(`api/workflow_api.py`)로 분리하는 것을 검토. 최소한 이 결정을 Task 8의 스텝에 명시("같은 파일에 추가 vs 분리" 판단 포함).

---

### 6. 기존 MVP 계획과의 관계 명시 필요

`2026-03-06-workflow-orchestration-mvp.md`가 여전히 존재합니다. 새 계획이 이를 대체하는 것인지, 확장하는 것인지 명시되어 있지 않습니다.

**권장:** 새 계획의 헤더에 `supersedes: docs/plans/2026-03-06-workflow-orchestration-mvp.md` 추가, 또는 기존 MVP 계획 상단에 "이 계획은 `2026-03-07-orchestration-engine-implementation-plan.md`로 대체됨" 표기.

---

## 잘 된 부분

- **12개 태스크의 의존성 순서**가 자연스러움 — 모델 먼저, 엔진 다음, API 마지막
- **설계 피드백 전체 반영** — 5-layer, source of truth, 멱등성, phase/status 분리, 리뷰 정규화, 전이 예시가 모두 구현 태스크에 매핑됨
- **TDD 접근 일관성** — 모든 태스크가 "실패 테스트 → 구현 → 통과" 패턴
- **대시보드 분리** — 엔진에만 집중, UI는 별도 트랙으로 올바르게 분리
- **헤드리스 퍼스트** — MCP 툴이 Task 11로 포함되어 있어 대시보드 없이도 동작 보장
- **Task 12의 전체 테스트 실행** — 최종 검증으로 회귀 방지

## 최종 판단

계획은 실행 가능한 수준입니다. 위 6개 보완 사항 중 **#1(CRUD API)과 #2(인덱서 호환)**은 누락이므로 추가 필요하고, 나머지는 선택적 개선입니다.

보완 후 바로 구현 시작해도 됩니다.
