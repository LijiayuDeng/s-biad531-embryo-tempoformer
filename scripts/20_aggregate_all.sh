#!/usr/bin/env bash
set -euo pipefail

# Thin shell wrapper around analysis/aggregate_matrix.py.

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

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
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
fi

DT="${DT_H:-0.25}"
T0="${T0_HPF:-4.5}"
"$PYTHON_BIN" analysis/aggregate_matrix.py \
  --outroot "$OUTROOT" \
  --dt "$DT" \
  --t0 "$T0" \
  --force "$FORCE"
