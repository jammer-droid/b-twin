---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# B-TWIN Release Checklist (P3)

## 1) Pre-flight
- [ ] `git status` clean
- [ ] Runtime mode validated (`btwin runtime show`)
- [ ] Config path/permissions checked
- [ ] `python scripts/doc_version_check.py`

## 2) Regression
- [ ] `.venv/bin/pytest -q tests/test_core tests/test_api tests/test_cli`
- [ ] No new failing/skipped critical suites

## 3) Recovery verification
- [ ] `./scripts/end_of_batch_sync.sh 200`
- [ ] `btwin indexer repair --doc-id <sample-doc>` tested
- [ ] `/api/ops/dashboard` shows non-broken payload

## 4) Performance sanity
- [ ] `btwin indexer refresh --limit 200` executed on staging dataset
- [ ] KPI snapshot recorded (`./scripts/collect_kpi_snapshot.py`)

## 5) Ops handoff
- [ ] Runbook updated (`docs/runbook.md`)
- [ ] Weekly KPI report generated (`./scripts/generate_weekly_kpi_report.py --week YYYY-WW`)
- [ ] Release note includes runtime mode impact (attached/standalone)
