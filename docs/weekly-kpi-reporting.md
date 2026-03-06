# Weekly KPI Reporting Procedure (P3)

## Schedule
- Snapshot collection: at least 1x per week (recommended daily)
- Weekly report generation: every Monday for previous/target ISO week

## Source logs
- KPI snapshot log: `<data_dir>/ops/kpi_snapshots.jsonl`
- End-of-batch run log: `<data_dir>/ops/end_of_batch_runs.jsonl`
- `data_dir` is resolved by BTWIN config precedence (`BTWIN_DATA_DIR` > project `.btwin` > `~/.btwin`)

## 1) Collect KPI snapshot
```bash
./scripts/collect_kpi_snapshot.py
```

Backfill / report reproduction:
```bash
./scripts/collect_kpi_snapshot.py --timestamp 2026-02-27T09:00:00+09:00
```

Snapshot row fields:
- `timestamp`
- `iso_week`
- `kpi.write_to_indexed_latency_ms_avg`
- `kpi.manifest_vector_mismatch_count`
- `kpi.repair_success_rate`
- `kpi.repair_avg_duration_ms`
- `gate_violation_count`

## 2) Generate weekly report markdown
```bash
./scripts/generate_weekly_kpi_report.py --week YYYY-WW
```

Output:
- `docs/reports/weekly-kpi/<YYYY-WW>.md`

Report includes:
- write_to_indexed_latency_ms_avg
- manifest_vector_mismatch_count
- repair_success_rate
- repair_avg_duration_ms
- gate violation count
- batch success rate
- top incident notes (max 3)
- actions for next week

## 3) End-of-batch logging (input for batch success rate)
Run end-of-batch sync using:
```bash
./scripts/end_of_batch_sync.sh 200
```

The script appends structured rows to `<data_dir>/ops/end_of_batch_runs.jsonl` with:
- `timestamp`
- `limit`
- `success`
- `duration_ms`
- `error`

## Guardrail
- If mismatch count > 0 for 2 consecutive weeks, open reliability task.
- If repair success rate < 0.98, schedule immediate postmortem.
- If batch success rate < 0.99, prioritize pipeline stabilization in next weekly actions.
