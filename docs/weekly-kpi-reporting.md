# Weekly KPI Reporting Procedure (P3)

## Schedule
- Every Monday 09:00 (local)
- Reporting window: previous 7 days

## Required KPI fields
- `write_to_indexed_latency_ms_avg`
- `manifest_vector_mismatch_count`
- `repair_success_rate`
- `repair_avg_duration_ms`
- Count of `gate_rejected` events

## Collection commands
```bash
btwin indexer kpi
curl -s http://127.0.0.1:8000/api/ops/dashboard | jq '.gateViolations | length'
```

## Report template
```text
Week: YYYY-WW
Latency(avg ms): <value>
Mismatch count: <value>
Repair success rate: <value>
Repair avg duration(ms): <value>
Gate violations: <value>
Top incident notes:
- ...
Actions for next week:
- ...
```

## Guardrail
- If mismatch count > 0 for 2 consecutive weeks, open reliability task.
- If repair success rate < 0.98, schedule immediate postmortem.
