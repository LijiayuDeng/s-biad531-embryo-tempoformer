#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Compare ETF S-BIAD840 external results against KimmelNet Table 1 values.
#
# Usage:
#   bash scripts/38_compare_sbiad840_kimmelnet.sh \
#     runs/sbiad840_eval_20260311_4models \
#     runs/sbiad840_eval_dense_cnn_single

BASE_OUTROOT="${1:-runs/sbiad840_eval_20260311_4models}"
DENSE_OUTROOT="${2:-runs/sbiad840_eval_dense_cnn_single}"
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" analysis/compare_sbiad840_kimmelnet.py \
  --base_csv "$BASE_OUTROOT/sbiad840_external_summary.csv" \
  --dense_csv "$DENSE_OUTROOT/sbiad840_external_summary.csv" \
  --out_csv "$BASE_OUTROOT/sbiad840_vs_kimmelnet.csv" \
  --out_md "$BASE_OUTROOT/sbiad840_vs_kimmelnet.md"

echo "[DONE] Comparison tables written under: $BASE_OUTROOT"
