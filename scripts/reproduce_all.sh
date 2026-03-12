#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
  set +a
fi

"$PYTHON_BIN" analysis/run_reproduction_pipeline.py "$@"
