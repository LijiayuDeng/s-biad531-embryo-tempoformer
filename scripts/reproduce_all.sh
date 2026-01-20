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

# Optional: saliency (qualitative, slow). Enable by setting RUN_SALIENCY=1
if [ "${RUN_SALIENCY:-0}" = "1" ]; then
  SAL_MODEL="${SALIENCY_MODEL:-full}"
  echo "[INFO] RUN_SALIENCY=1 -> running saliency for best ID28C5 embryo (model=$SAL_MODEL)"
  bash scripts/50_saliency_best_id28c5.sh "$OUTROOT" "$SAL_MODEL"
else
  echo "[INFO] RUN_SALIENCY=0 -> skip saliency (set RUN_SALIENCY=1 to enable)"
fi
