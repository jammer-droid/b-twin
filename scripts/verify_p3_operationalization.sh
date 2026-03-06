#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

.venv/bin/pytest -q \
  tests/test_core/test_runtime_adapters.py \
  tests/test_api/test_ops_dashboard_api.py \
  tests/test_api/test_runtime_config_api.py \
  tests/test_cli/test_runtime_cli.py

echo "[ok] P3 operationalization verification suite passed"
