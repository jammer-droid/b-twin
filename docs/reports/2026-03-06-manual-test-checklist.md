---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# B-TWIN 수동 테스트 체크리스트 (짧은 버전)

목적: 구현된 P1~P3 핵심 기능을 빠르게 수동 검증.

## 0) 준비

```bash
cd b-twin
uv sync
```

## 1) 런타임/어댑터 확인

```bash
uv run btwin runtime show
```

확인 포인트:
- attached면 `Recall adapter target: openclaw` 표시
- fallback 안내 문구 표시

## 2) Indexer KPI 확인

```bash
uv run btwin indexer kpi
```

확인 포인트:
- KPI 4종 필드가 출력되는지

## 3) Ops Dashboard 확인

```bash
uv run btwin serve-api
```

브라우저:
- `http://127.0.0.1:8000/ops`

확인 포인트:
- JSON 출력에 아래 키 존재
  - `indexerStatus`
  - `failureQueue`
  - `repairHistory`
  - `gateViolations`
  - `runtime.mode`
  - `runtime.recallAdapter`

## 4) 배치 동기화 파이프라인

```bash
./scripts/end_of_batch_sync.sh 5
```

확인 포인트:
- 정상 종료
- `.btwin/ops/end_of_batch_runs.jsonl`에 로그 1줄 추가

## 5) KPI 스냅샷/주간 리포트

```bash
./scripts/collect_kpi_snapshot.py
./scripts/generate_weekly_kpi_report.py --week 2026-10
```

확인 포인트:
- `.btwin/ops/kpi_snapshots.jsonl` 생성/갱신
- `docs/reports/weekly-kpi/2026-10.md` 생성

## 6) 문서 버전 검증

```bash
python scripts/doc_version_check.py
```

확인 포인트:
- `doc_version check OK` 출력

## 7) 전체 회귀(최종)

```bash
uv run pytest -q
```

통과 기준:
- 전체 테스트 성공 (현재 기준: `252 passed, 5 skipped`)
