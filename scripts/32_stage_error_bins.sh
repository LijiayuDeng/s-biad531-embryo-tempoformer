#!/usr/bin/env bash
set -euo pipefail

# Stage-stratified point-level error summary.
#
# Usage:
#   bash scripts/32_stage_error_bins.sh [OUTROOT] [OUT_CSV]
#
# Defaults:
#   OUTROOT = latest runs/paper_eval_*
#   OUT_CSV = <OUTROOT>/stage_error/stage_error_by_bin.csv
#
# Common environment overrides:
#   DATASETS=ID28C5_TEST,EXT25C_TEST
#   MODELS=cnn_single,full
#   SCHEME=kimmel_start
#   BINS=...   # only used when SCHEME=fixed

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,60p' "$0"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_shell_env.sh"
bootstrap_python_bin

OUTROOT="${1:-$(ls -dt "$ROOT"/runs/paper_eval_* 2>/dev/null | head -n 1)}"
OUT_CSV="${2:-$OUTROOT/stage_error/stage_error_by_bin.csv}"
DATASETS="${DATASETS:-ID28C5_TEST,EXT25C_TEST}"
MODELS="${MODELS:-cnn_single,full}"
SCHEME="${SCHEME:-kimmel_start}"
BINS="${BINS:-}"

[ -n "$OUTROOT" ] && [ -d "$OUTROOT" ] || { echo "[ERR] invalid OUTROOT: $OUTROOT"; exit 1; }

echo "[INFO] OUTROOT = $OUTROOT"
echo "[INFO] OUT_CSV = $OUT_CSV"
echo "[INFO] DATASETS = $DATASETS"
echo "[INFO] MODELS = $MODELS"
echo "[INFO] SCHEME = $SCHEME"
if [[ "$SCHEME" == "fixed" ]]; then
  echo "[INFO] BINS = $BINS"
fi

"$PYTHON_BIN" "$ROOT/analysis/stage_error_bins.py" \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --scheme "$SCHEME" \
  ${BINS:+--bins "$BINS"} \
  --out_csv "$OUT_CSV"
