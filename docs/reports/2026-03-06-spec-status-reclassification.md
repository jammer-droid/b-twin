---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# 2026-03-06 Spec Status Reclassification Summary

## Implemented specs (repo evidence)

1. **용어집 v1 + 용어 정렬**
   - `docs/glossary.md`
   - `docs/runbook.md` (용어 기준 링크)
   - `docs/reports/2026-03-05-btwin-openclaw-qa.md` (용어 기준 링크)

2. **핵심 문서 `doc_version` 필드 + 검증 스크립트**
   - `scripts/doc_version_check.py`
   - `README.md`, `CONTRIBUTING.md`, `docs/runbook.md`, `docs/indexer-operations.md`, `docs/release-checklist.md`, `docs/plans/2026-03-05-runtime-modes-and-core-ports.md`, `docs/reports/2026-03-05-btwin-openclaw-qa.md`

3. **`mark_pending` 사용/리뷰 규칙 공개**
   - `CONTRIBUTING.md` (`mark_pending` usage rules + reviewer checklist)

4. **배치 종료 기본 파이프라인 helper (`refresh + reconcile`)**
   - `scripts/end_of_batch_sync.sh`
   - `README.md` / `docs/runbook.md` / `docs/release-checklist.md` 실행 가이드 반영

5. **Runbook(`repair`) + KPI 리포팅 절차 문서화**
   - `docs/indexer-operations.md`
   - `docs/weekly-kpi-reporting.md`

## Pending specs (implementation gap 기준)

- 현재 즉시 실행 체크리스트 기준으로 **추가 구현 갭은 없음**.
- 남은 항목은 코드/문서 구현이 아닌 운영 실행 증적 수집 성격:
  - 2주 연속 KPI 리포트 축적
  - 운영환경 주간 파이프라인 성공률(99%+) 관측

## Release-time operational checks (not implementation blockers)

- 실제 운영 배치에서 `scripts/end_of_batch_sync.sh` 주간 성공률 측정
- 주간 KPI 리포트 2회 이상 발행 및 Top 3 원인/개선안 기록
- 스테이징/프로덕션에서 `python scripts/doc_version_check.py`를 release gate에 포함
