#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

if [ -f ".env" ]; then
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
fi

SOURCE_SPLIT="${SOURCE_SPLIT:-${SPLIT_28C5_SBIAD840:-./data/sbiad840_aligned_4p5/splits/28C5_sbiad840_test.json}}"
OUT_DIR="${1:-${OUT_DIR:-./data/sbiad840_aligned_4p5/splits/finetune}}"
TRAIN_COUNTS="${TRAIN_COUNTS:-12,24}"
VAL_COUNT="${VAL_COUNT:-12}"
SEED="${SEED:-42}"
PREFIX="${PREFIX:-28C5_sbiad840}"

echo "[INFO] SOURCE_SPLIT=$SOURCE_SPLIT"
echo "[INFO] OUT_DIR=$OUT_DIR"
echo "[INFO] TRAIN_COUNTS=$TRAIN_COUNTS VAL_COUNT=$VAL_COUNT SEED=$SEED PREFIX=$PREFIX"

"$PYTHON_BIN" analysis/make_sbiad840_finetune_splits.py \
  --source_split "$SOURCE_SPLIT" \
  --out_dir "$OUT_DIR" \
  --train_counts "$TRAIN_COUNTS" \
  --val_count "$VAL_COUNT" \
  --seed "$SEED" \
  --prefix "$PREFIX"
