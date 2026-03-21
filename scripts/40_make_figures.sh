#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

OUTROOT="${1:-}"
[ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT>"; exit 1; }
# shellcheck disable=SC1091
source scripts/_shell_env.sh
bootstrap_python_bin

"$PYTHON_BIN" analysis/make_figures_jobs.py --outroot "$OUTROOT"
echo "[OK] figures in $OUTROOT/figures_jobs"
