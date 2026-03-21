#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

# ============================================================
# Pick the "best" embryo on ID28C5_TEST (by minimal rmse_resid)
# and run SmoothGrad saliency for 5 clips (start=0/42/84/126/168).
#
# Usage:
#   bash scripts/50_saliency_best_id28c5.sh [OUTROOT] [model]
#
# Examples:
#   bash scripts/50_saliency_best_id28c5.sh
#   bash scripts/50_saliency_best_id28c5.sh ./runs/paper_eval_20260120_151431 full
#   bash scripts/50_saliency_best_id28c5.sh ./runs/paper_eval_20260120_151431 nocons
#
# Requirements:
# - You must have already run aggregation so that:
#   <OUTROOT>/ID28C5_TEST/<model>/embryo.csv exists
# - .env should point to processed_28C5 and ckpts, or you can export vars manually.
# ============================================================

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

OUTROOT="${1:-}"
MODEL="${2:-full}"

# auto-pick latest OUTROOT if not provided
if [ -z "$OUTROOT" ]; then
  OUTROOT="$(ls -dt "${RUNS_DIR:-./runs}"/paper_eval_* 2>/dev/null | head -n 1 || true)"
fi
[ -d "$OUTROOT" ] || { echo "[ERR] OUTROOT not found. Usage: $0 <OUTROOT> [model]"; exit 1; }

case "$MODEL" in
  cnn_single) CKPT="$CKPT_CNN_SINGLE" ;;
  meanpool)   CKPT="$CKPT_MEANPOOL" ;;
  nocons)     CKPT="$CKPT_NOCONS" ;;
  full)       CKPT="$CKPT_FULL" ;;
  *) echo "[ERR] model must be cnn_single|meanpool|nocons|full"; exit 1 ;;
esac

EMBRYO_CSV="$OUTROOT/ID28C5_TEST/$MODEL/embryo.csv"
if [ ! -f "$EMBRYO_CSV" ]; then
  echo "[ERR] missing $EMBRYO_CSV"
  echo "      You likely haven't aggregated yet. Run:"
  echo "      bash scripts/20_aggregate_all.sh $OUTROOT"
  exit 1
fi


# pick best EID by (rmse_resid, max_abs_resid)
EID="$("$PYTHON_BIN" analysis/select_best_embryo.py --embryo_csv "$EMBRYO_CSV")"

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] MODEL=$MODEL"
echo "[INFO] BEST_EID=$EID (by minimal rmse_resid, tie-breaker max_abs_resid)"

NPY="$PROC_28C5/$EID.npy"
if [ ! -f "$NPY" ]; then
  echo "[ERR] missing processed npy: $NPY"
  echo "      Check PROC_28C5 in .env"
  exit 1
fi

# output dir inside OUTROOT
OUTDIR="$OUTROOT/vis_best_${EID}_${MODEL}_smoothgrad_five"
mkdir -p "$OUTDIR"

# EMA flag
EMA_FLAG=""
if [ "${USE_EMA:-0}" = "1" ]; then
  EMA_FLAG="--use_ema"
fi

# AMP flag for saliency (usually OFF is fine; keep OFF by default)
AMP_FLAG=""
if [ "${SAL_AMP:-0}" = "1" ]; then
  AMP_FLAG="--amp"
fi

# visualization defaults (can override via env vars)
CLIP_LEN="${CLIP_LEN:-24}"
SG_N="${SAL_SG_N:-20}"
SG_SIGMA="${SAL_SG_SIGMA:-0.01}"
HM_LO="${SAL_HM_LO:-90}"
HM_HI="${SAL_HM_HI:-99.5}"
HM_GAMMA="${SAL_HM_GAMMA:-0.55}"
BLUR_K="${SAL_BLUR_K:-9}"
ALPHA_THR="${SAL_ALPHA_THR:-0.25}"
ALPHA_MAX="${SAL_ALPHA_MAX:-0.98}"

echo "[INFO] running SmoothGrad saliency (five clips) -> $OUTDIR"
PYTHONPATH=. "$PYTHON_BIN" analysis/vis_clip_saliency.py \
  --ckpt "$CKPT" \
  --npy  "$NPY" \
  --five \
  --clip_len "$CLIP_LEN" \
  --method smoothgrad \
  --sg_N "$SG_N" --sg_sigma "$SG_SIGMA" \
  --hm_lo "$HM_LO" --hm_hi "$HM_HI" --hm_gamma "$HM_GAMMA" --blur_k "$BLUR_K" \
  --alpha_thr "$ALPHA_THR" --alpha_max "$ALPHA_MAX" \
  --out_dir "$OUTDIR" \
  $EMA_FLAG $AMP_FLAG

echo "[DONE] saliency outputs in: $OUTDIR"
echo "       key file: $OUTDIR/saliency_time_overlay.png"
