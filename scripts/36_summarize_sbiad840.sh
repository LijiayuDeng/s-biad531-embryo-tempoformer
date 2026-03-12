#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

# Summarize completed S-BIAD840 external-domain evaluation into CSV + Markdown tables.
#
# Usage:
#   bash scripts/36_summarize_sbiad840.sh
#   bash scripts/36_summarize_sbiad840.sh runs/sbiad840_eval_20260311_4models

if [ -f ".env" ]; then
  eval "$("$PYTHON_BIN" analysis/dotenv_shell.py --env-file .env)"
fi

OUTROOT="${1:-${OUTROOT:-runs/sbiad840_eval_20260311_4models}}"
MODELS="${MODELS:-cnn_single,meanpool,nocons,full}"
DATASETS="${DATASETS:-SBIAD840_28C5_TEST,SBIAD840_25C_TEST}"

echo "[INFO] OUTROOT=$OUTROOT"
echo "[INFO] DATASETS=$DATASETS MODELS=$MODELS"

"$PYTHON_BIN" analysis/summarize_sbiad840_external.py \
  --outroot "$OUTROOT" \
  --datasets "$DATASETS" \
  --models "$MODELS"

echo "[DONE] External summary tables written under: $OUTROOT"
