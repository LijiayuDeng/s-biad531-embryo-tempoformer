#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/00_check_env.sh
bash scripts/10_infer_all.sh

# find latest OUTROOT
OUTROOT="$(ls -dt ./runs/paper_eval_* 2>/dev/null | head -n 1)"
echo "[INFO] using OUTROOT=$OUTROOT"

bash scripts/20_aggregate_all.sh "$OUTROOT"
bash scripts/30_ci_power_all.sh "$OUTROOT"
bash scripts/40_make_figures.sh "$OUTROOT"

echo "[DONE] All outputs under: $OUTROOT"
