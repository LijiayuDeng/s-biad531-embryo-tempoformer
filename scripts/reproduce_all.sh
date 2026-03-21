#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
fi

"$PYTHON_BIN" analysis/run_reproduction_pipeline.py "$@"
