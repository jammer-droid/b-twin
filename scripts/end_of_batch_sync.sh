#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-200}"
START_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
START_MS="$(uv run python - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"

DATA_DIR="$(uv run python - <<'PY'
from btwin.config import resolve_data_dir
print(resolve_data_dir())
PY
)"
OPS_DIR="${DATA_DIR}/ops"
LOG_PATH="${OPS_DIR}/end_of_batch_runs.jsonl"
mkdir -p "${OPS_DIR}"

if command -v btwin >/dev/null 2>&1; then
  BTWIN_CMD=(btwin)
else
  BTWIN_CMD=(uv run btwin)
fi

SUCCESS=true
ERROR_MESSAGE=""

run_step() {
  local label="$1"
  shift
  echo "${label}"
  "$@"
}

if ! run_step "[1/2] reconcile" "${BTWIN_CMD[@]}" indexer reconcile; then
  SUCCESS=false
  ERROR_MESSAGE="step failed: reconcile"
elif ! run_step "[2/2] refresh --limit ${LIMIT}" "${BTWIN_CMD[@]}" indexer refresh --limit "${LIMIT}"; then
  SUCCESS=false
  ERROR_MESSAGE="step failed: refresh"
fi

END_MS="$(uv run python - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"
DURATION_MS="$((END_MS - START_MS))"

uv run python - <<'PY' "$LOG_PATH" "$START_TS" "$LIMIT" "$SUCCESS" "$DURATION_MS" "$ERROR_MESSAGE"
import json
import sys

path, ts, limit, success, duration_ms, error = sys.argv[1:]
row = {
    "timestamp": ts,
    "limit": int(limit),
    "success": success.lower() == "true",
    "duration_ms": float(duration_ms),
    "error": error or None,
}
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
PY

if [[ "$SUCCESS" == "true" ]]; then
  echo "[ok] end-of-batch refresh+reconcile pipeline completed"
else
  echo "[error] end-of-batch refresh+reconcile pipeline failed"
  exit 1
fi
