#!/usr/bin/env bash
set -euo pipefail

# Summarize clip-length sensitivity into a compact context ladder and
# descriptive ETF-full 1/3/6 h linear fits.
#
# Usage:
#   bash scripts/12_cliplen_context_fit.sh [MAIN_OUTROOT] [CLIPLEN_OUTROOT] [OUT_DIR]
#
# Defaults:
#   MAIN_OUTROOT   = runs/paper_eval_20260225_232506
#   CLIPLEN_OUTROOT= runs/cliplen_sensitivity_20260311_030252
#   OUT_DIR        = <CLIPLEN_OUTROOT>/context_fit
#
# Example:
#   bash scripts/12_cliplen_context_fit.sh \
#     runs/paper_eval_20260225_232506 \
#     runs/cliplen_sensitivity_20260311_030252

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,40p' "$0"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

MAIN_OUTROOT="${1:-$ROOT/runs/paper_eval_20260225_232506}"
CLIPLEN_OUTROOT="${2:-$ROOT/runs/cliplen_sensitivity_20260311_030252}"
OUT_DIR="${3:-$CLIPLEN_OUTROOT/context_fit}"
CLIPLEN_CSV="${CLIPLEN_CSV:-$CLIPLEN_OUTROOT/cliplen_summary.csv}"

echo "[INFO] MAIN_OUTROOT   = $MAIN_OUTROOT"
echo "[INFO] CLIPLEN_OUTROOT= $CLIPLEN_OUTROOT"
echo "[INFO] CLIPLEN_CSV    = $CLIPLEN_CSV"
echo "[INFO] OUT_DIR        = $OUT_DIR"

"$PYTHON_BIN" "$ROOT/analysis/cliplen_context_fit.py" \
  --main_outroot "$MAIN_OUTROOT" \
  --cliplen_csv "$CLIPLEN_CSV" \
  --out_dir "$OUT_DIR"

