#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"
OUT_DIR="${1:-./runs/sbiad840_finetune_compare}"
OUT_CSV="${OUT_CSV:-$OUT_DIR/sbiad840_finetune_compare.csv}"
OUT_MD="${OUT_MD:-$OUT_DIR/sbiad840_finetune_compare.md}"

CNN_LABEL="${CNN_LABEL:-cnn_single_frame_tail1_ft12}"
CNN_RUN_DIR="${CNN_RUN_DIR:-}"
CNN_EVAL28_OUTROOT="${CNN_EVAL28_OUTROOT:-}"
CNN_EVAL25_OUTROOT="${CNN_EVAL25_OUTROOT:-}"

FULL_LABEL="${FULL_LABEL:-full_temporal_last1_ft12}"
FULL_RUN_DIR="${FULL_RUN_DIR:-}"
FULL_EVAL28_OUTROOT="${FULL_EVAL28_OUTROOT:-}"
FULL_EVAL25_OUTROOT="${FULL_EVAL25_OUTROOT:-}"

if [[ -z "$CNN_RUN_DIR" || -z "$CNN_EVAL28_OUTROOT" || -z "$CNN_EVAL25_OUTROOT" ]]; then
  echo "[ERR] Set CNN_RUN_DIR, CNN_EVAL28_OUTROOT, and CNN_EVAL25_OUTROOT"
  exit 1
fi
if [[ -z "$FULL_RUN_DIR" || -z "$FULL_EVAL28_OUTROOT" || -z "$FULL_EVAL25_OUTROOT" ]]; then
  echo "[ERR] Set FULL_RUN_DIR, FULL_EVAL28_OUTROOT, and FULL_EVAL25_OUTROOT"
  exit 1
fi

"$PYTHON_BIN" analysis/run_sbiad840_finetune_summary.py \
  --out_dir "$OUT_DIR" \
  --experiment "$CNN_LABEL" "$CNN_RUN_DIR" "$CNN_EVAL28_OUTROOT" "$CNN_EVAL25_OUTROOT" \
  --experiment "$FULL_LABEL" "$FULL_RUN_DIR" "$FULL_EVAL28_OUTROOT" "$FULL_EVAL25_OUTROOT" \
  --out_csv "$OUT_CSV" \
  --out_md "$OUT_MD"

echo "[DONE] Wrote comparison tables under: $OUT_DIR"
