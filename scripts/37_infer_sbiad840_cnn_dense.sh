#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

# Run a fairer KimmelNet-style dense single-frame external evaluation using ETF cnn_single.
#
# Usage:
#   bash scripts/37_infer_sbiad840_cnn_dense.sh
#   bash scripts/37_infer_sbiad840_cnn_dense.sh runs/sbiad840_eval_dense_cnn_single

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
fi

OUTROOT="${1:-${OUTROOT:-runs/sbiad840_eval_dense_cnn_single}}"
DATASETS="${DATASETS:-SBIAD840_28C5_TEST,SBIAD840_25C_TEST}"
DEVICE="${DEVICE:-auto}"
AMP="${AMP:-1}"
USE_EMA="${USE_EMA:-1}"
BATCH_SIZE="${BATCH_SIZE:-256}"

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] DATASETS=$DATASETS"
echo "[INFO] MODELS=cnn_single CLIP_LEN=1 STRIDE=1 BATCH_SIZE=$BATCH_SIZE"

DATASETS="$DATASETS" \
MODELS="cnn_single" \
CLIP_LEN=1 \
STRIDE=1 \
EXPECT_T="${EXPECT_T:-192}" \
IMG_SIZE="${IMG_SIZE:-384}" \
DEVICE="$DEVICE" \
AMP="$AMP" \
USE_EMA="$USE_EMA" \
BATCH_SIZE="$BATCH_SIZE" \
"$PYTHON_BIN" analysis/run_infer_matrix.py \
  --outroot "$OUTROOT" \
  --force "${FORCE:-0}" \
  --datasets "$DATASETS" \
  --models "cnn_single" \
  --clip_len 1 \
  --img_size "${IMG_SIZE:-384}" \
  --expect_t "${EXPECT_T:-192}" \
  --stride 1 \
  --device "$DEVICE" \
  --amp "$AMP" \
  --use_ema "$USE_EMA" \
  --batch_size "$BATCH_SIZE" \
  --proc_28c5 "${PROC_28C5:-}" \
  --proc_25c "${PROC_25C:-}" \
  --split_28c5 "${SPLIT_28C5:-}" \
  --split_25c "${SPLIT_25C:-}" \
  --proc_28c5_sbiad840 "${PROC_28C5_SBIAD840:-}" \
  --proc_25c_sbiad840 "${PROC_25C_SBIAD840:-}" \
  --split_28c5_sbiad840 "${SPLIT_28C5_SBIAD840:-}" \
  --split_25c_sbiad840 "${SPLIT_25C_SBIAD840:-}" \
  --ckpt_cnn_single "${CKPT_CNN_SINGLE:-}" \
  --ckpt_meanpool "${CKPT_MEANPOOL:-}" \
  --ckpt_nocons "${CKPT_NOCONS:-}" \
  --ckpt_full "${CKPT_FULL:-}"

echo "[DONE] Dense cnn_single inference written under: $OUTROOT"
