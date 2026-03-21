#!/usr/bin/env bash
set -euo pipefail

# Anchor (T0) sensitivity analysis by re-aggregating existing per-embryo infer JSONs.
#
# Usage:
#   bash scripts/33_anchor_sensitivity.sh [OUTROOT] [OUTDIR]
#
# Defaults:
#   OUTROOT = latest runs/paper_eval_*
#   OUTDIR  = <OUTROOT>/anchor_sensitivity
#
# Common environment overrides:
#   DATASETS=ID28C5_TEST,EXT25C_TEST
#   MODELS=cnn_single,meanpool,nocons,full
#   T0_LIST=4.0,4.5,5.0
#   DT_H=0.25
#   PYTHON_BIN=python

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,80p' "$0"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_shell_env.sh"
bootstrap_python_bin

OUTROOT="${1:-$(ls -dt "$ROOT"/runs/paper_eval_* 2>/dev/null | head -n 1)}"
OUTDIR="${2:-$OUTROOT/anchor_sensitivity}"
DATASETS="${DATASETS:-ID28C5_TEST,EXT25C_TEST}"
MODELS="${MODELS:-cnn_single,meanpool,nocons,full}"
T0_LIST="${T0_LIST:-4.0,4.5,5.0}"
DT="${DT_H:-0.25}"

[ -n "$OUTROOT" ] && [ -d "$OUTROOT" ] || { echo "[ERR] invalid OUTROOT: $OUTROOT"; exit 1; }

echo "[INFO] OUTROOT = $OUTROOT"
echo "[INFO] OUTDIR = $OUTDIR"
echo "[INFO] DATASETS = $DATASETS"
echo "[INFO] MODELS = $MODELS"
echo "[INFO] T0_LIST = $T0_LIST"
echo "[INFO] DT_H = $DT"

IFS=',' read -r -a DATASET_ARR <<< "$DATASETS"
IFS=',' read -r -a MODEL_ARR <<< "$MODELS"
IFS=',' read -r -a T0_ARR <<< "$T0_LIST"

mkdir -p "$OUTDIR"

for T0 in "${T0_ARR[@]}"; do
  T0_TRIM="$(echo "$T0" | xargs)"
  TAG="t0_${T0_TRIM//./p}"
  TDIR="$OUTDIR/$TAG"
  mkdir -p "$TDIR"

  for DS in "${DATASET_ARR[@]}"; do
    DS_TRIM="$(echo "$DS" | xargs)"
    for M in "${MODEL_ARR[@]}"; do
      M_TRIM="$(echo "$M" | xargs)"
      JSON_DIR="$OUTROOT/$DS_TRIM/$M_TRIM/json"
      ODIR="$TDIR/$DS_TRIM/$M_TRIM"
      mkdir -p "$ODIR"
      [ -d "$JSON_DIR" ] || { echo "[ERR] missing json dir: $JSON_DIR"; exit 1; }
      echo "[AGG] t0=$T0_TRIM  $DS_TRIM / $M_TRIM"
      "$PYTHON_BIN" "$ROOT/analysis/aggregate_kimmel.py" \
        --json_dir "$JSON_DIR" \
        --out_dir "$ODIR" \
        --dt "$DT" \
        --t0 "$T0_TRIM" >/dev/null
    done
  done
done

"$PYTHON_BIN" "$ROOT/analysis/anchor_sensitivity.py" \
  --outdir "$OUTDIR" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --out_csv "$OUTDIR/anchor_sensitivity_summary.csv"
