---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# B-TWIN Operations Runbook (P3)

> 용어 기준: `docs/glossary.md`

## Incident triage order
1. Check dashboard: `GET /api/ops/dashboard`
2. Check indexer counters: `btwin indexer status`
3. Check gate violations from dashboard payload (`gateViolations`)

## Common incidents

### A. Failure queue growth (`failed`/`stale`)
1. `./scripts/end_of_batch_sync.sh 500`
2. Repair top offenders from `failureQueue`
3. Re-check with `btwin indexer status`

### B. Gate rejection spike
1. Inspect recent `gateViolations`
2. Validate collab record checksum/vector presence
3. If persistent, run targeted repair for impacted `docId`

### C. Attached mode adapter errors
1. Validate OpenClaw config path (`btwin runtime show`)
2. Confirm runtime mode is `attached`
3. Fallback to standalone mode only for emergency continuity

## Recovery done criteria
- `indexerStatus.failed == 0`
- `indexerStatus.stale == 0` (or temporary known backlog)
- No new critical `gate_rejected` events in latest 30 min

## 프로젝트별 운영

### D. 프로젝트별 인덱서 상태 확인
```bash
# CLI
btwin indexer status                          # 전체

# HTTP API
GET /api/indexer/status?projectId=myproj      # 프로젝트별
GET /api/ops/dashboard?projectId=myproj       # 대시보드 (프로젝트 필터)
```

### E. 프로젝트 간 데이터 검색
- MCP proxy 경유 시 `scope`는 기본 `"project"` (해당 프로젝트만 검색)
- 전체 검색이 필요하면 HTTP API에서 `scope: "all"` 사용:
```json
POST /api/mcp/search
{"query": "keyword", "scope": "all"}
```

### F. 마이그레이션 후 reconcile
1. 마이그레이션 스크립트 실행: `python scripts/migrate_to_project_layout.py`
2. 인덱스 재조정: `btwin indexer reconcile`
3. 벡터 갱신: `btwin indexer refresh`
4. 상태 확인: `btwin indexer status` — `failed == 0`, `stale == 0` 검증

## Escalation
- If recovery loop fails 2 times, freeze write operations and escalate to maintainer.
