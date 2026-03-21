#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ ! -f ".env" ]; then
  echo "[ERR] .env not found. Run: cp .env.example .env  and edit paths."
  exit 1
fi

load_repo_env_if_present ".env"
OPTIONAL_ARGS=()
if [ -n "${WITH_OPTIONAL:-}" ]; then
  OPTIONAL_ARGS+=(--with-optional "$WITH_OPTIONAL")
fi
"$PYTHON_BIN" analysis/check_env.py "${OPTIONAL_ARGS[@]}"
