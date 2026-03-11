#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"
OUT_DIR="${1:-./runs/sbiad840_finetune_compare}"

"$PYTHON_BIN" analysis/summarize_sbiad840_transfer.py \
  --experiment \
    cnn_single_frame_tail1_ft12 \
    ./runs/finetune_cnn_single_ft12_frame_tail1_20260311_211714 \
    ./runs/sbiad840_ft12_frame_tail1_eval \
    ./runs/sbiad840_ft12_transfer_eval_25c \
  --experiment \
    full_temporal_last1_ft12 \
    ./runs/finetune_full_ft12_temporal_last1_20260311_224924 \
    ./runs/sbiad840_ft12_full_temporal_last1_eval \
    ./runs/sbiad840_ft12_transfer_eval_25c \
  --out_csv "$OUT_DIR/sbiad840_finetune_compare.csv" \
  --out_md "$OUT_DIR/sbiad840_finetune_compare.md"

echo "[DONE] Wrote comparison tables under: $OUT_DIR"
