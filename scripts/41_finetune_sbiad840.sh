#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"
MODEL="${MODEL:-cnn_single}"
STAGE="${STAGE:-head_only}"
SPLIT_JSON="${SPLIT_JSON:-./data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json}"
PROC_DIR="${PROC_DIR:-${PROC_28C5_SBIAD840:-./data/sbiad840_aligned_4p5/processed_28C5_sbiad840}}"
OUT_DIR="${1:-${OUT_DIR:-./runs/finetune_${MODEL}_${STAGE}_$(date +%Y%m%d_%H%M%S)}}"
DEVICE="${DEVICE:-auto}"
AMP="${AMP:-1}"
INIT_USE_EMA="${INIT_USE_EMA:-1}"
EMA_EVAL="${EMA_EVAL:-0}"
EPOCHS="${EPOCHS:-30}"
NUM_WORKERS="${NUM_WORKERS:-8}"
BATCH_SIZE="${BATCH_SIZE:-0}"
VAL_BATCH_SIZE="${VAL_BATCH_SIZE:-0}"
SAMPLES_PER_EMBRYO="${SAMPLES_PER_EMBRYO:-0}"
JITTER="${JITTER:--1}"
CACHE_ITEMS="${CACHE_ITEMS:--1}"
GRAD_ACCUM="${GRAD_ACCUM:-1}"
PATIENCE="${PATIENCE:-0}"
SAVE_EVERY="${SAVE_EVERY:-1}"
SEED="${SEED:-42}"
EMA_DECAY="${EMA_DECAY:-0.0}"
EMA_START_RATIO="${EMA_START_RATIO:-0.1}"
MEM_PROFILE="${MEM_PROFILE:-}"
LR="${LR:-0}"
INIT_CKPT="${INIT_CKPT:-}"

echo "[INFO] MODEL=$MODEL STAGE=$STAGE"
echo "[INFO] PROC_DIR=$PROC_DIR"
echo "[INFO] SPLIT_JSON=$SPLIT_JSON"
echo "[INFO] OUT_DIR=$OUT_DIR"

AMP_FLAG="--amp"
[ "$AMP" = "0" ] && AMP_FLAG="--no-amp"
INIT_EMA_FLAG="--init_use_ema"
[ "$INIT_USE_EMA" = "0" ] && INIT_EMA_FLAG="--no-init_use_ema"
EMA_EVAL_FLAG="--no-ema_eval"
[ "$EMA_EVAL" = "1" ] && EMA_EVAL_FLAG="--ema_eval"

CMD=(
  "$PYTHON_BIN" analysis/run_sbiad840_finetune.py
  --model "$MODEL"
  --stage "$STAGE"
  --split_json "$SPLIT_JSON"
  --proc_dir "$PROC_DIR"
  --out_dir "$OUT_DIR"
  --epochs "$EPOCHS"
  --num_workers "$NUM_WORKERS"
  --batch_size "$BATCH_SIZE"
  --val_batch_size "$VAL_BATCH_SIZE"
  --samples_per_embryo "$SAMPLES_PER_EMBRYO"
  --jitter "$JITTER"
  --cache_items "$CACHE_ITEMS"
  --grad_accum "$GRAD_ACCUM"
  --patience "$PATIENCE"
  --save_every "$SAVE_EVERY"
  --seed "$SEED"
  --device "$DEVICE"
  --lr "$LR"
  --mem_profile "$MEM_PROFILE"
  --ema_decay "$EMA_DECAY"
  --ema_start_ratio "$EMA_START_RATIO"
)

if [ -n "$INIT_CKPT" ]; then
  CMD+=(--init_ckpt "$INIT_CKPT")
fi
CMD+=("$AMP_FLAG" "$INIT_EMA_FLAG" "$EMA_EVAL_FLAG")

"${CMD[@]}"
