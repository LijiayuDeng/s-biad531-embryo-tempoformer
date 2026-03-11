#!/usr/bin/env bash
set -euo pipefail

# Thin shell wrapper around analysis/aggregate_matrix.py.

cd "$(dirname "$0")/.."

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
  # shellcheck disable=SC1091
  source .env
fi

DT="${DT_H:-0.25}"
T0="${T0_HPF:-4.5}"
PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" analysis/aggregate_matrix.py \
  --outroot "$OUTROOT" \
  --dt "$DT" \
  --t0 "$T0" \
  --force "$FORCE"
