#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .env

OUTROOT="${1:-}"
[ -d "$OUTROOT" ] || { echo "[ERR] Usage: $0 <OUTROOT>"; exit 1; }

for model in cnn_single meanpool nocons full; do
  A="$OUTROOT/EXT25C_TEST/$model/embryo.csv"
  B="$OUTROOT/ID28C5_TEST/$model/embryo.csv"
  [ -f "$A" ] || { echo "[ERR] missing $A"; exit 1; }
  [ -f "$B" ] || { echo "[ERR] missing $B"; exit 1; }

  echo "== CI & POWER for $model =="

  python3 analysis/ci_delta_m.py \
    --csv_a "$A" --csv_b "$B" \
    --label_a 25C --label_b 28C5 \
    --m_col m_anchor \
    --B 5000 --seed 0 \
    --out_json "$OUTROOT/CI_${model}_m_anchor.json"

  python3 analysis/power_curve.py \
    --csv_a "$A" --csv_b "$B" \
    --label_a 25C --label_b 28C5 \
    --m_col m_anchor \
    --R 500 --B 500 --seed 0 \
    --out_csv "$OUTROOT/power_${model}_m_anchor.csv" \
    --out_png "$OUTROOT/power_${model}_m_anchor.png"
done
