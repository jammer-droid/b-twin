#!/usr/bin/env -S uv run python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btwin.config import resolve_data_dir
from btwin.core.indexer import CoreIndexer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KPI + gate violation snapshot into JSONL.")
    parser.add_argument(
        "--timestamp",
        help="ISO-8601 timestamp for backfill/report reproduction (default: now, UTC)",
    )
    return parser.parse_args()


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _count_gate_violations(audit_path: Path) -> int:
    if not audit_path.exists():
        return 0

    count = 0
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("eventType") == "gate_rejected":
            count += 1
    return count


def main() -> int:
    args = parse_args()
    dt = _parse_timestamp(args.timestamp)
    data_dir = resolve_data_dir()

    indexer = CoreIndexer(data_dir=data_dir)
    kpi = indexer.kpi_summary()
    gate_violation_count = _count_gate_violations(data_dir / "audit.log.jsonl")

    snapshot = {
        "timestamp": dt.isoformat(),
        "iso_week": f"{dt.isocalendar().year}-{dt.isocalendar().week:02d}",
        "kpi": kpi,
        "gate_violation_count": gate_violation_count,
    }

    output_path = data_dir / "ops" / "kpi_snapshots.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

    print(f"snapshot_path={output_path}")
    print(json.dumps(snapshot, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
