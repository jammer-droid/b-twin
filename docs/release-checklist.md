# B-TWIN Release Checklist (P3)

## 1) Pre-flight
- [ ] `git status` clean
- [ ] Runtime mode validated (`btwin runtime show`)
- [ ] Config path/permissions checked

## 2) Regression
- [ ] `.venv/bin/pytest -q tests/test_core tests/test_api tests/test_cli`
- [ ] No new failing/skipped critical suites

## 3) Recovery verification
- [ ] `btwin indexer reconcile`
- [ ] `btwin indexer repair --doc-id <sample-doc>` tested
- [ ] `/api/ops/dashboard` shows non-broken payload

## 4) Performance sanity
- [ ] `btwin indexer refresh --limit 200` executed on staging dataset
- [ ] KPI snapshot recorded (`btwin indexer kpi`)

## 5) Ops handoff
- [ ] Runbook updated (`docs/runbook.md`)
- [ ] Weekly KPI report template prepared (`docs/weekly-kpi-reporting.md`)
- [ ] Release note includes runtime mode impact (attached/standalone)
