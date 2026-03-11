#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Default behavior:
#   - main benchmark: on
#   - continuous power curve: on
#   - clip-length sensitivity + context ladder: on
#   - stage-stratified point-level error bins: on
#   - anchor sensitivity: on
#   - saliency: off
#
# Optional toggles:
#   RUN_CONTINUOUS_POWER=0
#   RUN_CLIPLEN_SENSITIVITY=0
#   RUN_STAGE_ERROR_BINS=0
#   RUN_ANCHOR_SENSITIVITY=0
#   RUN_SALIENCY=1

bash scripts/00_check_env.sh
bash scripts/10_infer_all.sh

# find latest OUTROOT
OUTROOT="$(ls -dt ./runs/paper_eval_* 2>/dev/null | head -n 1)"
echo "[INFO] using OUTROOT=$OUTROOT"

bash scripts/20_aggregate_all.sh "$OUTROOT"

if [ "${RUN_STAGE_ERROR_BINS:-1}" = "1" ]; then
  echo "[INFO] RUN_STAGE_ERROR_BINS=1 -> running stage-stratified point-level error summary"
  bash scripts/32_stage_error_bins.sh "$OUTROOT" "$OUTROOT/stage_error/stage_error_by_bin.csv"
else
  echo "[INFO] RUN_STAGE_ERROR_BINS=0 -> skip stage-stratified point-level error summary"
fi

if [ "${RUN_ANCHOR_SENSITIVITY:-1}" = "1" ]; then
  echo "[INFO] RUN_ANCHOR_SENSITIVITY=1 -> running T0 anchor sensitivity summary"
  bash scripts/33_anchor_sensitivity.sh "$OUTROOT" "$OUTROOT/anchor_sensitivity"
else
  echo "[INFO] RUN_ANCHOR_SENSITIVITY=0 -> skip T0 anchor sensitivity summary"
fi

bash scripts/30_ci_power_all.sh "$OUTROOT"

if [ "${RUN_CONTINUOUS_POWER:-1}" = "1" ]; then
  echo "[INFO] RUN_CONTINUOUS_POWER=1 -> running continuous effect-size planning curve"
  bash scripts/31_power_curve_continuous.sh "$OUTROOT" "$OUTROOT/continuous_power"
else
  echo "[INFO] RUN_CONTINUOUS_POWER=0 -> skip continuous effect-size planning curve"
fi

if [ "${RUN_CLIPLEN_SENSITIVITY:-1}" = "1" ]; then
  CLIPLEN_OUTROOT="${CLIPLEN_OUTROOT:-$OUTROOT/cliplen_sensitivity}"
  echo "[INFO] RUN_CLIPLEN_SENSITIVITY=1 -> running fixed-checkpoint clip-length sensitivity"
  bash scripts/11_cliplen_sensitivity.sh "$CLIPLEN_OUTROOT"
  echo "[INFO] summarizing context ladder and ETF-full 1/3/6 h descriptive fits"
  bash scripts/12_cliplen_context_fit.sh "$OUTROOT" "$CLIPLEN_OUTROOT" "$CLIPLEN_OUTROOT/context_fit"
else
  echo "[INFO] RUN_CLIPLEN_SENSITIVITY=0 -> skip clip-length sensitivity/context ladder"
fi

bash scripts/40_make_figures.sh "$OUTROOT"

echo "[DONE] All outputs under: $OUTROOT"

# Optional: saliency (qualitative, slow). Enable by setting RUN_SALIENCY=1
if [ "${RUN_SALIENCY:-0}" = "1" ]; then
  SAL_MODEL="${SALIENCY_MODEL:-full}"
  echo "[INFO] RUN_SALIENCY=1 -> running saliency for best ID28C5 embryo (model=$SAL_MODEL)"
  bash scripts/50_saliency_best_id28c5.sh "$OUTROOT" "$SAL_MODEL"
else
  echo "[INFO] RUN_SALIENCY=0 -> skip saliency (set RUN_SALIENCY=1 to enable)"
fi
