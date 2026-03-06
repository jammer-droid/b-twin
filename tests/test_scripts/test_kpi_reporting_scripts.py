from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))


def _run_script(script: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_collect_kpi_snapshot_appends_jsonl_with_gate_count(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit = data_dir / "audit.log.jsonl"
    audit.write_text(
        "\n".join(
            [
                json.dumps({"eventType": "gate_rejected", "timestamp": "2026-03-01T00:00:00+00:00"}),
                json.dumps({"eventType": "gate_rejected", "timestamp": "2026-03-01T00:01:00+00:00"}),
                json.dumps({"eventType": "indexer_refresh", "timestamp": "2026-03-01T00:02:00+00:00"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["BTWIN_DATA_DIR"] = str(data_dir)

    ts = "2026-03-02T10:00:00+09:00"
    res = _run_script("collect_kpi_snapshot.py", ["--timestamp", ts], env)
    assert res.returncode == 0, res.stderr

    snapshot_path = data_dir / "ops" / "kpi_snapshots.jsonl"
    assert snapshot_path.exists()
    row = json.loads(snapshot_path.read_text(encoding="utf-8").strip().splitlines()[-1])

    assert row["timestamp"] == ts
    assert row["gate_violation_count"] == 2
    assert "write_to_indexed_latency_ms_avg" in row["kpi"]


def test_generate_weekly_kpi_report_from_logs(tmp_path: Path):
    data_dir = tmp_path / "data"
    ops_dir = data_dir / "ops"
    ops_dir.mkdir(parents=True, exist_ok=True)

    snapshots = [
        {
            "timestamp": "2026-03-03T09:00:00+09:00",
            "kpi": {
                "write_to_indexed_latency_ms_avg": 120.5,
                "manifest_vector_mismatch_count": 1,
                "repair_success_rate": 0.95,
                "repair_avg_duration_ms": 200.0,
            },
            "gate_violation_count": 3,
        }
    ]
    (ops_dir / "kpi_snapshots.jsonl").write_text(
        "\n".join(json.dumps(row) for row in snapshots) + "\n",
        encoding="utf-8",
    )

    batch_logs = [
        {
            "timestamp": "2026-03-03T08:00:00+09:00",
            "limit": 200,
            "success": True,
            "duration_ms": 1800.0,
            "error": None,
        },
        {
            "timestamp": "2026-03-04T08:00:00+09:00",
            "limit": 200,
            "success": False,
            "duration_ms": 900.0,
            "error": "refresh failed",
        },
    ]
    (ops_dir / "end_of_batch_runs.jsonl").write_text(
        "\n".join(json.dumps(row) for row in batch_logs) + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["BTWIN_DATA_DIR"] = str(data_dir)

    week = "2026-10"
    out_dir = str(tmp_path / "reports")
    res = _run_script("generate_weekly_kpi_report.py", ["--week", week, "--output-dir", out_dir], env)
    assert res.returncode == 0, res.stderr

    report_path = tmp_path / "reports" / f"{week}.md"
    assert report_path.exists()
    body = report_path.read_text(encoding="utf-8")

    assert "write_to_indexed_latency_ms_avg" in body
    assert "manifest_vector_mismatch_count" in body
    assert "repair_success_rate" in body
    assert "repair_avg_duration_ms" in body
    assert "gate violation count" in body
    assert "batch success rate" in body
    assert "Top incident notes" in body
    assert "Actions for next week" in body


def test_count_gate_violations_uses_bounded_tail(tmp_path: Path):
    """_count_gate_violations reads only the last 200 audit entries, not the entire file."""
    from collect_kpi_snapshot import _count_gate_violations

    audit_path = tmp_path / "audit.log.jsonl"

    # Write 210 lines: 205 gate_rejected + 5 other events
    lines = []
    for i in range(205):
        lines.append(json.dumps({"eventType": "gate_rejected", "timestamp": f"2026-03-01T00:{i:04d}"}))
    for i in range(5):
        lines.append(json.dumps({"eventType": "indexer_refresh", "timestamp": f"2026-03-01T01:{i:04d}"}))
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    count = _count_gate_violations(audit_path)

    # With bounded tail(limit=200), we only see the last 200 lines.
    # Last 200 lines = 5 indexer_refresh + 195 gate_rejected (from the end)
    # So count should be less than 205 (the total gate_rejected in the file)
    assert count < 205
    # The last 200 lines contain 195 gate_rejected events
    assert count == 195


def test_count_gate_violations_returns_zero_for_missing_file(tmp_path: Path):
    """_count_gate_violations returns 0 when audit file does not exist."""
    from collect_kpi_snapshot import _count_gate_violations

    missing = tmp_path / "nonexistent.jsonl"
    assert _count_gate_violations(missing) == 0
