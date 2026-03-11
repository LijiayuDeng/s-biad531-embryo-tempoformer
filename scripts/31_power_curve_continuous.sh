#!/usr/bin/env bash
set -euo pipefail

# Run the continuous effect-size planning curve analysis.
#
# Usage:
#   bash scripts/31_power_curve_continuous.sh [OUTROOT] [OUT_DIR]
#
# Defaults:
#   OUTROOT = runs/paper_eval_20260225_232506
#   OUT_DIR = <OUTROOT>/continuous_power
#
# Common environment overrides:
#   MODELS=cnn_single,meanpool,nocons,full
#   A_TEST=EXT25C_TEST
#   B_TEST=ID28C5_TEST
#   M_COL=m_anchor
#   E_LIST=2,3,4,6,8,10,12,14,16,18,20,22
#   DELTA_MAX=0.10
#   DELTA_STEP=0.002
#   R_OUTER=1200
#   B_BOOT=800
#   SEED=20260310
#   Y_MIN_PLOT=0
#   Y_MAX_PLOT=23
#   Y_TICK_STEP=1
#   ENFORCE_MONOTONE_POWER_E=1
#   ENFORCE_MONOTONE_THRESHOLD_DELTA=1
#
# Example:
#   bash scripts/31_power_curve_continuous.sh \
#     runs/paper_eval_20260225_232506 \
#     runs/paper_eval_20260225_232506/continuous_power

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,80p' "$0"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

OUTROOT="${1:-$ROOT/runs/paper_eval_20260225_232506}"
OUT_DIR="${2:-$OUTROOT/continuous_power}"

MODELS="${MODELS:-cnn_single,meanpool,nocons,full}"
A_TEST="${A_TEST:-EXT25C_TEST}"
B_TEST="${B_TEST:-ID28C5_TEST}"
M_COL="${M_COL:-m_anchor}"
E_LIST="${E_LIST:-2,3,4,6,8,10,12,14,16,18,20,22}"
DELTA_MAX="${DELTA_MAX:-0.10}"
DELTA_STEP="${DELTA_STEP:-0.002}"
R_OUTER="${R_OUTER:-1200}"
B_BOOT="${B_BOOT:-800}"
SEED="${SEED:-20260310}"
Y_MIN_PLOT="${Y_MIN_PLOT:-0}"
Y_MAX_PLOT="${Y_MAX_PLOT:-23}"
Y_TICK_STEP="${Y_TICK_STEP:-1}"
ENFORCE_MONOTONE_POWER_E="${ENFORCE_MONOTONE_POWER_E:-1}"
ENFORCE_MONOTONE_THRESHOLD_DELTA="${ENFORCE_MONOTONE_THRESHOLD_DELTA:-1}"

echo "[INFO] OUTROOT                         = $OUTROOT"
echo "[INFO] OUT_DIR                         = $OUT_DIR"
echo "[INFO] MODELS                          = $MODELS"
echo "[INFO] A_TEST / B_TEST                 = $A_TEST / $B_TEST"
echo "[INFO] DELTA_MAX / DELTA_STEP          = $DELTA_MAX / $DELTA_STEP"
echo "[INFO] R_OUTER / B_BOOT / SEED         = $R_OUTER / $B_BOOT / $SEED"
echo "[INFO] MONOTONE(power_E/threshold_d)   = $ENFORCE_MONOTONE_POWER_E / $ENFORCE_MONOTONE_THRESHOLD_DELTA"

"$PYTHON_BIN" "$ROOT/analysis/power_curve_continuous.py" \
  --outroot "$OUTROOT" \
  --out_dir "$OUT_DIR" \
  --models "$MODELS" \
  --a_test "$A_TEST" \
  --b_test "$B_TEST" \
  --m_col "$M_COL" \
  --E_list "$E_LIST" \
  --delta_max "$DELTA_MAX" \
  --delta_step "$DELTA_STEP" \
  --R "$R_OUTER" \
  --B_boot "$B_BOOT" \
  --seed "$SEED" \
  --y_min_plot "$Y_MIN_PLOT" \
  --y_max_plot "$Y_MAX_PLOT" \
  --y_tick_step "$Y_TICK_STEP" \
  --enforce_monotone_power_e "$ENFORCE_MONOTONE_POWER_E" \
  --enforce_monotone_threshold_delta "$ENFORCE_MONOTONE_THRESHOLD_DELTA"
