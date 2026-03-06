#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-200}"

echo "[1/2] reconcile"
btwin indexer reconcile

echo "[2/2] refresh --limit ${LIMIT}"
btwin indexer refresh --limit "${LIMIT}"

echo "[ok] end-of-batch refresh+reconcile pipeline completed"
