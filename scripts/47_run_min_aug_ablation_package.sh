#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

OUTROOT="${1:-${OUTROOT:-./runs/min_aug_ablation_$(date +%Y%m%d_%H%M%S)}}"
SETTINGS="${SETTINGS:-baseline_full,no_spatial,no_photometric,no_acquisition,no_temporal_sampling}"
DATASETS="${DATASETS:-ID28C5_TEST,EXT25C_TEST}"
MODEL="${MODEL:-full}"
GPU_PRESET="${GPU_PRESET:-rtx5090}"
FORCE_INFER="${FORCE_INFER:-1}"
FORCE_AGG="${FORCE_AGG:-1}"
RUN_TRAIN="${RUN_TRAIN:-1}"
RUN_EVAL="${RUN_EVAL:-1}"
RUN_SUMMARY="${RUN_SUMMARY:-1}"

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] SETTINGS=$SETTINGS"
echo "[INFO] DATASETS=$DATASETS"
echo "[INFO] MODEL=$MODEL"
echo "[INFO] GPU_PRESET=$GPU_PRESET"

if [ "$MODEL" != "full" ]; then
  echo "[ERR] This helper is intentionally restricted to MODEL=full."
  exit 1
fi

if [ "$RUN_TRAIN" = "1" ]; then
  SETTINGS="$SETTINGS" bash scripts/45_train_full_aug_ablation.sh "$OUTROOT"
fi

if [ "$RUN_EVAL" = "1" ]; then
  IFS=',' read -r -a settings_arr <<< "$SETTINGS"
  for raw in "${settings_arr[@]}"; do
    setting="$(echo "$raw" | xargs)"
    [ -n "$setting" ] || continue

    ckpt="$OUTROOT/$setting/best.pt"
    eval_outroot="$OUTROOT/$setting/eval_main"

    if [ ! -f "$ckpt" ]; then
      echo "[ERR] Missing checkpoint for setting=$setting: $ckpt"
      exit 1
    fi

    echo "[RUN] evaluate $setting"
    "$PYTHON_BIN" analysis/run_infer_matrix.py \
      --outroot "$eval_outroot" \
      --force "$FORCE_INFER" \
      --datasets "$DATASETS" \
      --models "$MODEL" \
      --clip_len "${CLIP_LEN:-24}" \
      --img_size "${IMG_SIZE:-384}" \
      --expect_t "${EXPECT_T:-192}" \
      --stride "${STRIDE:-8}" \
      --device "${DEVICE:-auto}" \
      --amp "${AMP:-1}" \
      --use_ema "${USE_EMA:-1}" \
      --batch_size "${BATCH_SIZE:-64}" \
      --proc_28c5 "${PROC_28C5:-}" \
      --proc_25c "${PROC_25C:-}" \
      --split_28c5 "${SPLIT_28C5:-}" \
      --split_25c "${SPLIT_25C:-}" \
      --ckpt_full "$ckpt"

    "$PYTHON_BIN" analysis/aggregate_matrix.py \
      --outroot "$eval_outroot" \
      --datasets "$DATASETS" \
      --models "$MODEL" \
      --dt "${DT_H:-0.25}" \
      --t0 "${T0_HPF:-4.5}" \
      --force "$FORCE_AGG"
  done
fi

if [ "$RUN_SUMMARY" = "1" ]; then
  "$PYTHON_BIN" analysis/summarize_min_aug_ablation.py \
    --outroot "$OUTROOT" \
    --settings "$SETTINGS" \
    --datasets "$DATASETS" \
    --model "$MODEL"
fi

echo "[DONE] Minimal augmentation ablation package ready under: $OUTROOT"
