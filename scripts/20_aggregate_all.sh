#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Aggregate per-embryo infer JSONs into points/embryo/summary
# ------------------------------------------------------------
# Usage:
#   bash scripts/20_aggregate_all.sh <OUTROOT> [--force]
#
# Examples:
#   bash scripts/20_aggregate_all.sh ./runs/paper_eval_20260119_175146
#   bash scripts/20_aggregate_all.sh ./runs/paper_eval_20260119_175146 --force
#
# If OUTROOT is omitted, uses the latest ./runs/paper_eval_*
# ============================================================

cd "$(dirname "$0")/.."

FORCE=0
OUTROOT=""

# parse args
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *)
      if [ -z "$OUTROOT" ]; then OUTROOT="$arg"; fi
      ;;
  esac
done

# load env if present (optional but recommended)
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
fi

DT="${DT_H:-0.25}"
T0="${T0_HPF:-4.5}"
PYTHON_BIN="${PYTHON_BIN:-python}"

# auto-pick OUTROOT if missing
if [ -z "$OUTROOT" ]; then
  OUTROOT="$(ls -dt ./runs/paper_eval_* 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$OUTROOT" ] || [ ! -d "$OUTROOT" ]; then
  echo "[ERR] OUTROOT not found."
  echo "Usage: $0 <OUTROOT> [--force]"
  echo "Example: $0 ./runs/paper_eval_20260119_175146"
  exit 1
fi

AGG_SCRIPT="analysis/aggregate_kimmel.py"
if [ ! -f "$AGG_SCRIPT" ]; then
  echo "[ERR] missing $AGG_SCRIPT"
  echo "You need analysis/aggregate_kimmel.py in repo."
  exit 1
fi

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] dt_h=$DT  t0_hpf=$T0  force=$FORCE"

datasets=(ID28C5_TEST EXT25C_TEST)
models=(cnn_single meanpool nocons full)

# helper: check json_dir contains json
count_json () {
  local d="$1"
  find "$d" -maxdepth 1 -type f -name "*.json" | wc -l
}

for ds in "${datasets[@]}"; do
  for m in "${models[@]}"; do
    JSON_DIR="$OUTROOT/$ds/$m/json"
    OUT_DIR="$OUTROOT/$ds/$m"
    SUM_JSON="$OUT_DIR/summary.json"

    if [ ! -d "$JSON_DIR" ]; then
      echo "[WARN] missing json_dir: $JSON_DIR  (skip)"
      continue
    fi

    njson="$(count_json "$JSON_DIR")"
    if [ "$njson" -eq 0 ]; then
      echo "[WARN] no json files in: $JSON_DIR  (skip)"
      continue
    fi

    if [ "$FORCE" -eq 0 ] && [ -f "$SUM_JSON" ]; then
      echo "[SKIP] $ds/$m already aggregated (found summary.json)"
      continue
    fi

    echo "[AGG] $ds / $m  (json=$njson)"
    mkdir -p "$OUT_DIR"

    "$PYTHON_BIN" "$AGG_SCRIPT" \
      --json_dir "$JSON_DIR" \
      --out_dir  "$OUT_DIR" \
      --dt "$DT" \
      --t0 "$T0"
  done
done

echo "[DONE] Aggregation complete under: $OUTROOT"
