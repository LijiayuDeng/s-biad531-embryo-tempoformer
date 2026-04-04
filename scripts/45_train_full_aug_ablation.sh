#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

OUTROOT="${1:-${OUTROOT:-${RUNS_DIR:-./runs}/aug_ablation_full_$(date +%Y%m%d_%H%M%S)}}"
PROC_DIR="${PROC_DIR:-${PROC_28C5:-}}"
SPLIT_JSON="${SPLIT_JSON:-${SPLIT_28C5:-}}"
SETTINGS="${SETTINGS:-baseline_full,no_spatial,no_photometric,no_acquisition,no_temporal_sampling}"
DRY_RUN="${DRY_RUN:-0}"

DEVICE="${DEVICE:-cuda}"
AMP="${AMP:-1}"
USE_EMA_FLAG="${USE_EMA_FLAG:---ema_eval}"
MEM_PROFILE="${MEM_PROFILE:-lowmem}"
EPOCHS="${EPOCHS:-300}"
# Default to a long-run sweet spot on the 32 GiB RTX 5090: aggressive enough
# to retain most of the throughput gain over the released 32/64 setup, while
# leaving more headroom than the ~29 GiB bs64/val128 configuration.
BATCH_SIZE="${BATCH_SIZE:-48}"
VAL_BATCH_SIZE="${VAL_BATCH_SIZE:-96}"
NUM_WORKERS="${NUM_WORKERS:-16}"
SAMPLES_PER_EMBRYO="${SAMPLES_PER_EMBRYO:-32}"
CACHE_ITEMS="${CACHE_ITEMS:-16}"
GRAD_ACCUM="${GRAD_ACCUM:-1}"
SAVE_EVERY="${SAVE_EVERY:-25}"
PATIENCE="${PATIENCE:-0}"
SEED="${SEED:-42}"
LR="${LR:-0.0006}"
WEIGHT_DECAY="${WEIGHT_DECAY:-0.01}"
WARMUP_RATIO="${WARMUP_RATIO:-0.01}"
LR_MIN_RATIO="${LR_MIN_RATIO:-0.05}"
MAX_GRAD_NORM="${MAX_GRAD_NORM:-1.0}"
LAMBDA_ABS="${LAMBDA_ABS:-1.0}"
LAMBDA_DIFF="${LAMBDA_DIFF:-1.0}"
CONS_RAMP_RATIO="${CONS_RAMP_RATIO:-0.2}"
ABS_LOSS_TYPE="${ABS_LOSS_TYPE:-l1}"
EMA_DECAY="${EMA_DECAY:-0.99}"
EMA_START_RATIO="${EMA_START_RATIO:-0.0}"

CLIP_LEN="${CLIP_LEN:-24}"
IMG_SIZE="${IMG_SIZE:-384}"
EXPECT_T="${EXPECT_T:-192}"
MODEL_DIM="${MODEL_DIM:-128}"
MODEL_DEPTH="${MODEL_DEPTH:-4}"
MODEL_HEADS="${MODEL_HEADS:-4}"
MODEL_MLP_RATIO="${MODEL_MLP_RATIO:-2.0}"
DROP="${DROP:-0.1}"
ATTN_DROP="${ATTN_DROP:-0.0}"
TEMPORAL_DROP_P="${TEMPORAL_DROP_P:-0.05}"
TEMPORAL_MODE="${TEMPORAL_MODE:-transformer}"
CNN_BASE="${CNN_BASE:-32}"
CNN_EXPAND="${CNN_EXPAND:-2}"
CNN_SE_REDUCTION="${CNN_SE_REDUCTION:-4}"

mkdir -p "$OUTROOT/logs"
MANIFEST="$OUTROOT/manifest.tsv"
cat > "$MANIFEST" <<'EOF'
setting	out_dir	log_file	aug_disable_groups	jitter	seed
EOF

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] PROC_DIR=$PROC_DIR"
echo "[INFO] SPLIT_JSON=$SPLIT_JSON"
echo "[INFO] SETTINGS=$SETTINGS"
echo "[INFO] PYTHON_BIN=$PYTHON_BIN"

AMP_FLAG="--amp"
[ "$AMP" = "0" ] && AMP_FLAG="--no-amp"

run_one() {
  local setting="$1"
  local disable_groups="$2"
  local jitter="$3"
  local out_dir="$OUTROOT/$setting"
  local log_file="$OUTROOT/logs/$setting.log"

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$setting" "$out_dir" "$log_file" "${disable_groups:-none}" "$jitter" "$SEED" >> "$MANIFEST"

  local -a cmd=(
    "$PYTHON_BIN" src/EmbryoTempoFormer.py train
    --proc_dir "$PROC_DIR"
    --split_json "$SPLIT_JSON"
    --out_dir "$out_dir"
    --epochs "$EPOCHS"
    --batch_size "$BATCH_SIZE"
    --val_batch_size "$VAL_BATCH_SIZE"
    --num_workers "$NUM_WORKERS"
    --samples_per_embryo "$SAMPLES_PER_EMBRYO"
    --jitter "$jitter"
    --aug_disable_groups "$disable_groups"
    --cache_items "$CACHE_ITEMS"
    --grad_accum "$GRAD_ACCUM"
    --save_every "$SAVE_EVERY"
    --patience "$PATIENCE"
    --clip_len "$CLIP_LEN"
    --img_size "$IMG_SIZE"
    --expect_t "$EXPECT_T"
    --lr "$LR"
    --weight_decay "$WEIGHT_DECAY"
    --warmup_ratio "$WARMUP_RATIO"
    --lr_min_ratio "$LR_MIN_RATIO"
    --max_grad_norm "$MAX_GRAD_NORM"
    --model_dim "$MODEL_DIM"
    --model_depth "$MODEL_DEPTH"
    --model_heads "$MODEL_HEADS"
    --model_mlp_ratio "$MODEL_MLP_RATIO"
    --drop "$DROP"
    --attn_drop "$ATTN_DROP"
    --temporal_drop_p "$TEMPORAL_DROP_P"
    --temporal_mode "$TEMPORAL_MODE"
    --cnn_base "$CNN_BASE"
    --cnn_expand "$CNN_EXPAND"
    --cnn_se_reduction "$CNN_SE_REDUCTION"
    --mem_profile "$MEM_PROFILE"
    --lambda_abs "$LAMBDA_ABS"
    --lambda_diff "$LAMBDA_DIFF"
    --cons_ramp_ratio "$CONS_RAMP_RATIO"
    --abs_loss_type "$ABS_LOSS_TYPE"
    --ema_decay "$EMA_DECAY"
    --ema_start_ratio "$EMA_START_RATIO"
    --seed "$SEED"
    --device "$DEVICE"
    "$AMP_FLAG"
    "$USE_EMA_FLAG"
  )

  echo
  echo "[RUN] $setting"
  echo "[RUN] out_dir=$out_dir"
  echo "[RUN] log_file=$log_file"
  echo "[RUN] aug_disable_groups=${disable_groups:-<none>} jitter=$jitter"

  if [ "$DRY_RUN" = "1" ]; then
    printf '[DRY] '
    printf '%q ' "${cmd[@]}"
    printf '\n'
    return 0
  fi

  "${cmd[@]}" 2>&1 | tee "$log_file"
}

IFS=',' read -r -a settings_arr <<< "$SETTINGS"
for raw in "${settings_arr[@]}"; do
  setting="$(echo "$raw" | xargs)"
  case "$setting" in
    baseline_full)
      run_one "$setting" "" 2
      ;;
    no_spatial)
      run_one "$setting" "spatial" 2
      ;;
    no_photometric)
      run_one "$setting" "photometric" 2
      ;;
    no_acquisition)
      run_one "$setting" "acquisition" 2
      ;;
    no_temporal_sampling)
      run_one "$setting" "temporal" 0
      ;;
    *)
      echo "[ERR] Unknown setting: $setting"
      exit 1
      ;;
  esac
done

echo
echo "[DONE] Full augmentation ablation outputs under: $OUTROOT"
echo "[DONE] Manifest: $MANIFEST"
