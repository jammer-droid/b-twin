#!/usr/bin/env -S uv run python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btwin.config import resolve_data_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate weekly KPI markdown report from snapshot + batch logs.")
    parser.add_argument("--week", required=True, help="ISO week in YYYY-WW format")
    return parser.parse_args()


def _parse_week(value: str) -> tuple[int, int]:
    try:
        year_s, week_s = value.split("-", maxsplit=1)
        year, week = int(year_s), int(week_s)
    except ValueError as exc:
        raise ValueError("week must be YYYY-WW") from exc
    if week < 1 or week > 53:
        raise ValueError("week must be between 01 and 53")
    return year, week


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _filter_week(rows: list[dict[str, Any]], year: int, week: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        dt = _parse_ts(str(row.get("timestamp", "")))
        if dt is None:
            continue
        iso = dt.isocalendar()
        if iso.year == year and iso.week == week:
            selected.append(row)
    return selected


def _fmt_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)
    return str(value)


def main() -> int:
    args = parse_args()
    year, week = _parse_week(args.week)

    data_dir = resolve_data_dir()
    ops_dir = data_dir / "ops"

    snapshots = _filter_week(_read_jsonl(ops_dir / "kpi_snapshots.jsonl"), year, week)
    snapshots.sort(key=lambda row: row.get("timestamp", ""))

    batch_runs = _filter_week(_read_jsonl(ops_dir / "end_of_batch_runs.jsonl"), year, week)
    total_batches = len(batch_runs)
    success_batches = sum(1 for row in batch_runs if bool(row.get("success")))
    batch_success_rate = (success_batches / total_batches) if total_batches > 0 else None

    latest_snapshot = snapshots[-1] if snapshots else {}
    kpi = latest_snapshot.get("kpi", {}) if isinstance(latest_snapshot.get("kpi", {}), dict) else {}
    gate_violation_count = latest_snapshot.get("gate_violation_count")

    incidents: list[str] = []
    failed_runs = [row for row in batch_runs if not bool(row.get("success"))]
    if failed_runs:
        latest_failure = failed_runs[-1]
        incidents.append(
            f"Batch failures {len(failed_runs)}/{total_batches}; latest error: {latest_failure.get('error') or 'unknown'}"
        )
    if isinstance(gate_violation_count, int) and gate_violation_count > 0:
        incidents.append(f"Gate violations recorded: {gate_violation_count}")
    mismatch = kpi.get("manifest_vector_mismatch_count")
    if isinstance(mismatch, (int, float)) and mismatch > 0:
        incidents.append(f"Manifest/vector mismatch remains: {mismatch}")
    incidents = incidents[:3]

    actions: list[str] = []
    if isinstance(batch_success_rate, float) and batch_success_rate < 0.99:
        actions.append("Stabilize end-of-batch pipeline and investigate recent failures.")
    if isinstance(mismatch, (int, float)) and mismatch > 0:
        actions.append("Run reconcile + targeted repair for mismatched documents.")
    repair_success_rate = kpi.get("repair_success_rate")
    if isinstance(repair_success_rate, (int, float)) and repair_success_rate < 0.98:
        actions.append("Schedule reliability review for low repair success rate.")
    if not actions:
        actions.append("Maintain current operations and continue weekly monitoring.")

    report_dir = Path("docs/reports/weekly-kpi")
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"{args.week}.md"

    lines = [
        f"# Weekly KPI Report ({args.week})",
        "",
        f"- snapshot count: {len(snapshots)}",
        f"- batch runs: {total_batches}",
        "",
        "## KPI",
        f"- write_to_indexed_latency_ms_avg: {_fmt_number(kpi.get('write_to_indexed_latency_ms_avg'))}",
        f"- manifest_vector_mismatch_count: {_fmt_number(kpi.get('manifest_vector_mismatch_count'), digits=0)}",
        f"- repair_success_rate: {_fmt_number(kpi.get('repair_success_rate'))}",
        f"- repair_avg_duration_ms: {_fmt_number(kpi.get('repair_avg_duration_ms'))}",
        f"- gate violation count: {_fmt_number(gate_violation_count, digits=0)}",
        f"- batch success rate: {_fmt_number(batch_success_rate)}",
        "",
        "## Top incident notes",
    ]

    if incidents:
        lines.extend(f"- {item}" for item in incidents)
    else:
        lines.append("- No notable incidents in this week.")

    lines.extend(["", "## Actions for next week"])
    lines.extend(f"- {item}" for item in actions)
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report_path={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
