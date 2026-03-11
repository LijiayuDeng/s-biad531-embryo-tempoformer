#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

OUTROOT="${1:-}"
[ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT>"; exit 1; }
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" analysis/make_figures_jobs.py --outroot "$OUTROOT"
echo "[OK] figures in $OUTROOT/figures_jobs"
