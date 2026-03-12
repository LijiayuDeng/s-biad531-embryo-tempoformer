#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

# Aggregate completed S-BIAD840 external-domain JSON outputs.
#
# Usage:
#   bash scripts/35_aggregate_sbiad840.sh
#   bash scripts/35_aggregate_sbiad840.sh runs/sbiad840_eval_20260311_4models

if [ -f ".env" ]; then
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
fi

OUTROOT="${1:-${OUTROOT:-runs/sbiad840_eval_20260311_4models}}"
DT="${DT_H:-0.25}"
T0="${T0_HPF:-4.5}"
MODELS="${MODELS:-cnn_single,meanpool,nocons,full}"
DATASETS="${DATASETS:-SBIAD840_28C5_TEST,SBIAD840_25C_TEST}"
FORCE="${FORCE:-1}"

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] DATASETS=$DATASETS MODELS=$MODELS"

"$PYTHON_BIN" analysis/aggregate_matrix.py \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --dt "$DT" \
  --t0 "$T0" \
  --force "$FORCE"

echo "[DONE] Aggregated external-domain outputs under: $OUTROOT"
