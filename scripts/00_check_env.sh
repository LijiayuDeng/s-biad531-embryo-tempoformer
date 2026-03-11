#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f ".env" ]; then
  echo "[ERR] .env not found. Run: cp .env.example .env  and edit paths."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a
PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" analysis/check_env.py
