#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Thin orchestration wrapper for multi-dataset / multi-model inference.
#
# Usage:
#   bash scripts/10_infer_all.sh
#   bash scripts/10_infer_all.sh ./runs/paper_eval_manual
#
# Common overrides:
#   DATASETS=ID28C5_TEST
#   MODELS=full
#   PYTHON_BIN=python
#   OUTROOT=./runs/paper_eval_manual

if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
OUTROOT="${1:-${OUTROOT:-}}"

"$PYTHON_BIN" analysis/run_infer_matrix.py \
  --outroot "$OUTROOT" \
  --datasets "${DATASETS:-ID28C5_TEST,EXT25C_TEST}" \
  --models "${MODELS:-cnn_single,meanpool,nocons,full}" \
  --clip_len "${CLIP_LEN:-24}" \
  --img_size "${IMG_SIZE:-384}" \
  --expect_t "${EXPECT_T:-192}" \
  --stride "${STRIDE:-8}" \
  --device "${DEVICE:-auto}" \
  --amp "${AMP:-1}" \
  --use_ema "${USE_EMA:-1}" \
  --batch_size "${BATCH_SIZE:-64}" \
  --proc_28c5 "$PROC_28C5" \
  --proc_25c "$PROC_25C" \
  --split_28c5 "$SPLIT_28C5" \
  --split_25c "$SPLIT_25C" \
  --ckpt_cnn_single "$CKPT_CNN_SINGLE" \
  --ckpt_meanpool "$CKPT_MEANPOOL" \
  --ckpt_nocons "$CKPT_NOCONS" \
  --ckpt_full "$CKPT_FULL"
