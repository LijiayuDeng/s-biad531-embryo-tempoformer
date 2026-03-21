#!/usr/bin/env bash
set -euo pipefail

# Direct stage-dependent / non-linear tempo analysis from aggregated points.csv.
#
# Usage:
#   bash scripts/44_stage_tempo_dependence.sh [OUTROOT] [OUT_DIR]
#
# Defaults:
#   OUTROOT = latest runs/paper_eval_*
#   OUT_DIR = <OUTROOT>/stage_tempo
#
# Common environment overrides:
#   DATASETS=ID28C5_TEST,EXT25C_TEST
#   MODELS=cnn_single,meanpool,nocons,full

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,40p' "$0"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_shell_env.sh"
bootstrap_python_bin

OUTROOT="${1:-$(ls -dt "$ROOT"/runs/paper_eval_* 2>/dev/null | head -n 1)}"
OUT_DIR="${2:-$OUTROOT/stage_tempo}"
DATASETS="${DATASETS:-ID28C5_TEST,EXT25C_TEST}"
MODELS="${MODELS:-cnn_single,meanpool,nocons,full}"
N_BOOT="${N_BOOT:-3000}"
SEED="${SEED:-42}"

[ -n "$OUTROOT" ] && [ -d "$OUTROOT" ] || { echo "[ERR] invalid OUTROOT: $OUTROOT"; exit 1; }

echo "[INFO] OUTROOT = $OUTROOT"
echo "[INFO] OUT_DIR = $OUT_DIR"
echo "[INFO] DATASETS = $DATASETS"
echo "[INFO] MODELS = $MODELS"
echo "[INFO] N_BOOT = $N_BOOT"
echo "[INFO] SEED = $SEED"

"$PYTHON_BIN" "$ROOT/analysis/stage_tempo_dependence.py" \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS" \
  --out_dir "$OUT_DIR" \
  --n_boot "$N_BOOT" \
  --seed "$SEED"
