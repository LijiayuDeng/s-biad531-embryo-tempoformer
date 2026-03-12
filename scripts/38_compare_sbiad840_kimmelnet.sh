#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Compare ETF S-BIAD840 external results against KimmelNet Table 1 values
# using the same through-origin y = mx summary quantities.
#
# Usage:
#   bash scripts/38_compare_sbiad840_kimmelnet.sh \
#     ./runs/sbiad840_eval_zero_shot \
#     ./runs/sbiad840_eval_dense_cnn_single
#
# Or equivalently:
#   BASE_OUTROOT=./runs/sbiad840_eval_zero_shot \
#   DENSE_OUTROOT=./runs/sbiad840_eval_dense_cnn_single \
#   bash scripts/38_compare_sbiad840_kimmelnet.sh

BASE_OUTROOT="${1:-${BASE_OUTROOT:-}}"
DENSE_OUTROOT="${2:-${DENSE_OUTROOT:-}}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -z "$BASE_OUTROOT" || -z "$DENSE_OUTROOT" ]]; then
  echo "[ERR] Provide BASE_OUTROOT and DENSE_OUTROOT as positional args or env vars"
  exit 1
fi

"$PYTHON_BIN" analysis/compare_sbiad840_kimmelnet.py \
  --base_csv "$BASE_OUTROOT/sbiad840_external_summary.csv" \
  --dense_csv "$DENSE_OUTROOT/sbiad840_external_summary.csv" \
  --out_csv "$BASE_OUTROOT/sbiad840_vs_kimmelnet.csv" \
  --out_md "$BASE_OUTROOT/sbiad840_vs_kimmelnet.md"

echo "[DONE] Comparison tables written under: $BASE_OUTROOT"
