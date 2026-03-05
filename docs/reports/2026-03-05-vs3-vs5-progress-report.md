# B-TWIN VS3–VS5 Progress Report

Date: 2026-03-05
Author: codex-code
Branch: `feature/vs3-vs5`

---

## Update (VS6 통합 완료)

본 문서는 원래 VS3~VS5 진행 보고서였고, 이후 VS6가 `main`에 통합되었습니다.

- VS6 통합 커밋: `80a8595` (`merge: integrate VS6 core indexer into main`)
- VS6 핵심 반영:
  - Core indexer (`refresh/reconcile/repair`)
  - index manifest + status model (`pending/indexed/stale/failed/deleted`)
  - BTwin write path indexer 연동
  - CLI/API indexer 운영 명령 추가
  - document contracts 1차 검증 추가
- 통합 이후 전체 테스트:
  - `uv run --python 3.13 pytest -q` → **200 passed, 5 skipped**

상세 운영 가이드는 `docs/indexer-operations.md` 참고.

## 1) 요약

VS3~VS5를 subagent-driven-development 방식(작은 청크 + 테스트 + 리뷰)으로 진행했고,
현재 브랜치 기준 구현/테스트가 모두 완료된 상태입니다.

현재 전체 테스트 결과:
- `pytest` → **178 passed, 5 skipped**

---

## 2) VS3 (운영 배치/스케줄/히스토리)

### 구현 사항
1. Promotion 스케줄 설정 모델 추가
   - `BTwinConfig.promotion.enabled`
   - `BTwinConfig.promotion.schedule` (기본: `0 9,21 * * *`)
2. CLI 스케줄 관리 추가
   - `btwin promotion schedule`
   - `btwin promotion schedule --set "<cron>"`
3. Promoted history UI 추가
   - `/ui/promoted`
   - `/api/promotions/history` 데이터 기반 렌더링

### 관련 커밋
- `b7a6ff4` feat(vs3): promotion schedule config + CLI
- `0ecf0eb` fix(vs3): schedule CLI write-safety/cron-validation/type-hardening
- `130d751` feat(vs3): promoted history dashboard

### 테스트
- `tests/test_core/test_config_promotion.py`
- `tests/test_cli/test_promotion_schedule_cli.py`
- `tests/test_api/test_promoted_ui.py`

---

## 3) VS4 (Convo 명시 기록 + 필터 검색 + 엔트리 뷰 분리)

### 구현 사항
1. Convo 명시 기록 경로 추가
   - storage: `entries/convo/YYYY-MM-DD/*.md`
   - core: `BTwin.record_convo(...)`
   - mcp: `btwin_convo_record(content, requested_by_user=False)`
2. 검색 메타 필터 추가
   - vector search: `metadata_filters`
   - core search: `filters` 전달
   - mcp search: `record_type` optional filter
3. 엔트리 통합 조회 + 필터 UI
   - API: `GET /api/entries?recordType=`
   - UI: `/ui/entries`
   - 필터: `all | entry | convo | collab`

### 관련 커밋
- `8e6af1d` feat(vs4): explicit convo record + record-type filtered search/ui

### 테스트
- `tests/test_core/test_convo_storage.py`
- `tests/test_core/test_vector_filters.py`
- `tests/test_mcp/test_convo_record.py`
- `tests/test_api/test_entries_api.py`
- `tests/test_api/test_entries_ui.py`
- `tests/test_core/test_btwin.py`, `tests/test_mcp/test_server.py` 확장

---

## 4) VS5 (운영 안정화/감사 로그)

### 구현 사항
1. 감사 로그 모듈 추가
   - `src/btwin/core/audit.py` (`AuditLogger`, JSONL)
2. API 게이트/승격 이벤트 감사
   - gate reject 이벤트
   - gate success 이벤트 (`gate_handoff_succeeded`, `gate_complete_succeeded`)
   - promotion proposed / approved / batch run 이벤트
3. MCP 측 감사 이벤트
   - `btwin_convo_record` 실행 이벤트 기록
4. 민감 데이터 엔드포인트 보호
   - `GET /api/entries`, `GET /api/promotions/history`를 admin token scoped로 보호

### 관련 커밋
- `2dde18c` feat(vs5): audit logging for gate/promotion across API/MCP
- `e625dfb` fix(vs5): admin-scoped data endpoints + gate success audit events

### 테스트
- `tests/test_core/test_audit.py`
- `tests/test_api/test_audit_integration.py`

---

## 5) 품질/보안 관점 반영 사항

- admin reload 토큰 필수 + actor binding 강화(이전 단계에서 반영, VS3~5에서도 유지)
- 에러 엔벨로프 통일 유지 (`errorCode/message/details/traceId`)
- 배치/승격 흐름에 대해 상태 전이/권한 체크 일관성 유지

---

## 6) 현재 브랜치 상태

- 브랜치: `feature/vs3-vs5`
- 워킹 트리: clean
- 테스트: green (173/5)
- 머지 준비 상태

---

## 7) 남은 후속(선택)

- MCP 도구에 promotion 전용 툴셋(approve/run/history) 추가 확장
- audit 이벤트 레벨/샘플링/보관 정책 세분화
- production 환경에서 cron 스케줄러와의 자동 실행 연동
