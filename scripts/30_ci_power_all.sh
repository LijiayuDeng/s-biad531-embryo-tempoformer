#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

if [ -f ".env" ]; then
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

OUTROOT="${1:-}"
[ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT>"; exit 1; }
"$PYTHON_BIN" analysis/run_ci_power_matrix.py --outroot "$OUTROOT"
