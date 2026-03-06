---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# B-TWIN 피처별 구현/테스트 가이드 (P1~P3)

이 문서는 현재 `main`에 반영된 P1~P3 구현을 사용자 관점에서 빠르게 검증할 수 있도록 정리한 가이드입니다.

## 0) 사전 준비

```bash
cd b-twin
uv sync
```

---

## 1) Runtime 모드/어댑터 (attached/standalone)

### 구현 목적
- 런타임 모드에 따라 recall/audit 동작을 분리하고,
- attached에서 OpenClaw 메모리 바인딩이 없을 때 degraded 상태를 명시적으로 노출.

### 구현 기능
- `src/btwin/core/runtime_adapters.py`
  - `build_runtime_adapters()`가 `recall_backend`, `degraded`, `degraded_reason` 제공
  - OpenClaw recall numeric 파싱 강건화
- `src/btwin/api/collab_api.py`
  - `/api/ops/dashboard`에 runtime 상태 상세 필드 노출
- `src/btwin/cli/main.py`
  - `btwin runtime show`에 target/fallback 메시지 출력

### 테스트 방법
```bash
uv run pytest -q tests/test_core/test_runtime_adapters.py
uv run pytest -q tests/test_api/test_ops_dashboard_api.py
uv run pytest -q tests/test_cli/test_runtime_cli.py
uv run btwin runtime show
```

---

## 2) Indexer KPI 계측 (P1-1)

### 구현 목적
- sync gap/복구 상태를 운영 지표로 관측 가능하게 만들기.

### 구현 기능
- `src/btwin/core/indexer.py`
  - `kpi_summary()`
  - `write→indexed latency`, `manifest↔vector mismatch`, `repair 성공률/평균시간`
  - malformed/NaN/Inf KPI 값 방어
- API/CLI 노출
  - `GET /api/indexer/kpi`
  - `btwin indexer kpi`

### 테스트 방법
```bash
uv run pytest -q tests/test_core/test_indexer.py tests/test_api/test_indexer_api.py tests/test_cli/test_indexer_cli.py
uv run btwin indexer kpi
```

---

## 3) Handoff/Complete 정합성 게이트 (P1-2)

### 구현 목적
- 상태 전이(handoff/complete) 전에 indexed+checksum 일치 상태를 강제.

### 구현 기능
- `src/btwin/api/collab_api.py`
  - `_enforce_integrity_gate()`
  - 실패 시 repair 재시도 후 `INTEGRITY_GATE_FAILED(409)` 반환
- `src/btwin/core/indexer.py`
  - `verify_doc_integrity(doc_id)`

### 테스트 방법
```bash
uv run pytest -q tests/test_api/test_collab_api.py tests/test_core/test_indexer.py
```

---

## 4) 리콜 품질 개선 (P1-3)

### 구현 목적
- 검색 품질(정확도/다양성/최신성/반복호출 비용) 개선.

### 구현 기능
- `src/btwin/core/vector.py`
  - Hybrid score(lexical + vector)
  - MMR rerank
  - Temporal decay
  - search cache
- `src/btwin/core/btwin.py`
  - 고급 검색 파라미터 pass-through

### 테스트 방법
```bash
uv run pytest -q tests/test_core/test_vector.py tests/test_core/test_btwin.py
```

---

## 5) Ops Dashboard (P2-3)

### 구현 목적
- 운영 상태를 한 눈에 확인 가능한 API/UI 제공.

### 구현 기능
- `GET /api/ops/dashboard`
  - `indexerStatus`, `failureQueue`, `repairHistory`, `gateViolations`, `runtime.*`
- `GET /ops`
  - Admin token 입력 후 로드 가능한 UI

### 테스트 방법
```bash
uv run pytest -q tests/test_api/test_ops_dashboard_api.py
# 로컬 서버로 수동 확인
uv run btwin serve-api
# 브라우저: http://127.0.0.1:8000/ops
```

---

## 6) 운영 자동화 스크립트 (P3 운영화)

### 구현 목적
- 배치 종료 동기화와 KPI 수집/주간 리포트를 자동화.

### 구현 기능
- `scripts/end_of_batch_sync.sh`
  - `refresh + reconcile` 실행
  - `<data_dir>/ops/end_of_batch_runs.jsonl` 기록
- `scripts/collect_kpi_snapshot.py`
  - `<data_dir>/ops/kpi_snapshots.jsonl` 스냅샷 누적
- `scripts/generate_weekly_kpi_report.py`
  - `docs/reports/weekly-kpi/<YYYY-WW>.md` 생성

### 테스트 방법
```bash
./scripts/end_of_batch_sync.sh 5
./scripts/collect_kpi_snapshot.py
./scripts/collect_kpi_snapshot.py --timestamp 2026-02-27T09:00:00+09:00
./scripts/generate_weekly_kpi_report.py --week 2026-09
./scripts/generate_weekly_kpi_report.py --week 2026-10
uv run pytest -q tests/test_scripts/test_kpi_reporting_scripts.py
```

---

## 7) 문서 메타데이터 검증

### 구현 목적
- 관리 문서의 `doc_version` 누락 방지.

### 구현 기능
- `scripts/doc_version_check.py`

### 테스트 방법
```bash
python scripts/doc_version_check.py
python scripts/doc_version_check.py docs/runbook.md docs/indexer-operations.md
```

---

## 8) 전체 회귀(권장)

```bash
uv run pytest -q
```

기대 결과(현재 기준):
- `252 passed, 5 skipped`
