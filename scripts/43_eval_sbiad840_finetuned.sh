#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
else
  echo "[ERR] .env not found."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
OUTROOT="${1:-${OUTROOT:-./runs/sbiad840_finetuned_eval}}"
DATASETS="${DATASETS:-SBIAD840_25C_TEST}"
MODELS="${MODELS:-cnn_single,full}"
DEVICE="${DEVICE:-cuda}"
AMP="${AMP:-1}"
USE_EMA="${USE_EMA:-1}"
BATCH_SIZE="${BATCH_SIZE:-64}"

CKPT_CNN_SINGLE_FT="${CKPT_CNN_SINGLE_FT:-}"
CKPT_FULL_FT="${CKPT_FULL_FT:-}"

if [ -z "$CKPT_CNN_SINGLE_FT" ] || [ -z "$CKPT_FULL_FT" ]; then
  echo "[ERR] Set CKPT_CNN_SINGLE_FT and CKPT_FULL_FT"
  exit 1
fi

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] DATASETS=$DATASETS MODELS=$MODELS"

"$PYTHON_BIN" analysis/run_infer_matrix.py \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --clip_len "${CLIP_LEN:-24}" \
  --img_size "${IMG_SIZE:-384}" \
  --expect_t "${EXPECT_T:-192}" \
  --stride "${STRIDE:-8}" \
  --device "$DEVICE" \
  --amp "$AMP" \
  --use_ema "$USE_EMA" \
  --batch_size "$BATCH_SIZE" \
  --proc_28c5 "$PROC_28C5" \
  --proc_25c "$PROC_25C" \
  --split_28c5 "$SPLIT_28C5" \
  --split_25c "$SPLIT_25C" \
  --proc_28c5_sbiad840 "$PROC_28C5_SBIAD840" \
  --proc_25c_sbiad840 "$PROC_25C_SBIAD840" \
  --split_28c5_sbiad840 "$SPLIT_28C5_SBIAD840" \
  --split_25c_sbiad840 "$SPLIT_25C_SBIAD840" \
  --ckpt_cnn_single "$CKPT_CNN_SINGLE_FT" \
  --ckpt_meanpool "$CKPT_MEANPOOL" \
  --ckpt_nocons "$CKPT_NOCONS" \
  --ckpt_full "$CKPT_FULL_FT"

"$PYTHON_BIN" analysis/aggregate_matrix.py \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --dt "${DT_H:-0.25}" \
  --t0 "${T0_HPF:-4.5}" \
  --force 1

"$PYTHON_BIN" analysis/summarize_sbiad840_external.py \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS"

echo "[DONE] Fine-tuned S-BIAD840 evaluation written under: $OUTROOT"
