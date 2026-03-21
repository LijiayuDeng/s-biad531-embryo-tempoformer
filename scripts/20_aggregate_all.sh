#!/usr/bin/env bash
set -euo pipefail

# Thin shell wrapper around analysis/aggregate_matrix.py.

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

OUTROOT=""
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *)
      if [ -z "$OUTROOT" ]; then OUTROOT="$arg"; fi
      ;;
  esac
done

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
fi

if [ -z "$OUTROOT" ]; then
  OUTROOT="$(ls -dt ./runs/paper_eval_* 2>/dev/null | head -n 1 || true)"
fi
[ -n "$OUTROOT" ] && [ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT> [--force]"; exit 1; }

DT="${DT_H:-0.25}"
T0="${T0_HPF:-4.5}"
"$PYTHON_BIN" analysis/aggregate_matrix.py \
  --outroot "$OUTROOT" \
  --dt "$DT" \
  --t0 "$T0" \
  --force "$FORCE"
