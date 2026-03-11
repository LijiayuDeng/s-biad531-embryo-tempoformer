#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Fixed-sampling clip-length sensitivity evaluation
# ------------------------------------------------------------
# This script evaluates inference-time sensitivity to shorter
# temporal context at the same underlying 15 min sampling
# interval. It does NOT create denser/sparser acquisition.
#
# Default behavior:
#   - models:   full
#   - datasets: ID28C5_TEST,EXT25C_TEST
#   - clip_len: 4,12,24
#
# Interpretation:
#   - cnn_single from the main benchmark serves as the 0 h / single-frame
#     reference.
#   - This script evaluates ETF-full at 1 h / 3 h / 6 h context under the same
#     15 min sampling interval.
#
# Output layout:
#   <OUTROOT>/L04/ID28C5_TEST/full/json/*.json
#   <OUTROOT>/L04/ID28C5_TEST/full/{points,embryo,summary}.csv/json
#   ...
#   <OUTROOT>/cliplen_summary.csv
#
# Usage:
#   bash scripts/11_cliplen_sensitivity.sh
#   bash scripts/11_cliplen_sensitivity.sh ./runs/cliplen_eval_xxx
#
# Optional env overrides:
#   CLIP_LENS=4,12,24
#   MODELS=full
#   DATASETS=ID28C5_TEST,EXT25C_TEST
#   STRIDE=8
#   FORCE=1
#   MAX_EIDS=1
#   PYTHON_BIN=python
# ============================================================

cd "$(dirname "$0")/.."

if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
fi

stamp="$(date +%Y%m%d_%H%M%S)"
OUTROOT="${1:-${RUNS_DIR:-./runs}/cliplen_sensitivity_${stamp}}"
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" analysis/run_cliplen_sensitivity.py \
  --outroot "$OUTROOT" \
  --clip_lens "${CLIP_LENS:-4,12,24}" \
  --models "${MODELS:-full}" \
  --datasets "${DATASETS:-ID28C5_TEST,EXT25C_TEST}" \
  --dt_h "${DT_H:-0.25}" \
  --t0_hpf "${T0_HPF:-4.5}" \
  --img_size "${IMG_SIZE:-384}" \
  --expect_t "${EXPECT_T:-192}" \
  --stride "${STRIDE:-8}" \
  --device "${DEVICE:-auto}" \
  --amp "${AMP:-1}" \
  --use_ema "${USE_EMA:-1}" \
  --batch_size "${BATCH_SIZE:-64}" \
  --max_eids "${MAX_EIDS:-0}" \
  --force "${FORCE:-0}" \
  --proc_28c5 "$PROC_28C5" \
  --proc_25c "$PROC_25C" \
  --split_28c5 "$SPLIT_28C5" \
  --split_25c "$SPLIT_25C" \
  --ckpt_cnn_single "$CKPT_CNN_SINGLE" \
  --ckpt_meanpool "$CKPT_MEANPOOL" \
  --ckpt_nocons "$CKPT_NOCONS" \
  --ckpt_full "$CKPT_FULL"
