#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

OUTROOT="${1:-}"
[ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT>"; exit 1; }
"$PYTHON_BIN" analysis/run_ci_power_matrix.py --outroot "$OUTROOT"
