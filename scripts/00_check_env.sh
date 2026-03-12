#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

if [ ! -f ".env" ]; then
  echo "[ERR] .env not found. Run: cp .env.example .env  and edit paths."
  exit 1
fi

set -a
# shellcheck disable=SC1091
eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
set +a
OPTIONAL_ARGS=()
if [ -n "${WITH_OPTIONAL:-}" ]; then
  OPTIONAL_ARGS+=(--with-optional "$WITH_OPTIONAL")
fi
"$PYTHON_BIN" analysis/check_env.py "${OPTIONAL_ARGS[@]}"
