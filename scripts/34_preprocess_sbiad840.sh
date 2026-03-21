#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

# Convert the S-BIAD840 Princeton_Data PNG export into ETF-style processed npy.
#
# Default usage:
#   bash scripts/34_preprocess_sbiad840.sh
#   bash scripts/34_preprocess_sbiad840.sh ./data/sbiad840_aligned_4p5
#
# Custom usage:
#   SBIAD840_SRC_ROOT=/path/to/s-biad840/Files/Princeton_Data \
#   SBIAD840_OUT_ROOT=./data/sbiad840_aligned_4p5 \
#   ALIGN_START_HPF=4.5 \
#   bash scripts/34_preprocess_sbiad840.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
fi

SRC_ROOT="${SRC_ROOT:-${SBIAD840_SRC_ROOT:-/home/lichi/work/s-biad840/Files/Princeton_Data}}"
OUT_ROOT="${1:-${OUT_ROOT:-${SBIAD840_OUT_ROOT:-./data/sbiad840_aligned_4p5}}}"
ALIGN_START_HPF="${ALIGN_START_HPF:-4.5}"
EXPECT_T="${EXPECT_T:-192}"
IMG_SIZE="${IMG_SIZE:-384}"
P_LO="${P_LO:-1}"
P_HI="${P_HI:-99}"
PAD_TO_EXPECT="${PAD_TO_EXPECT:-0}"
LIMIT="${LIMIT:-0}"

echo "[INFO] SRC_ROOT=$SRC_ROOT"
echo "[INFO] OUT_ROOT=$OUT_ROOT"
echo "[INFO] ALIGN_START_HPF=$ALIGN_START_HPF EXPECT_T=$EXPECT_T IMG_SIZE=$IMG_SIZE P_LO=$P_LO P_HI=$P_HI PAD_TO_EXPECT=$PAD_TO_EXPECT LIMIT=$LIMIT"


"$PYTHON_BIN" analysis/preprocess_sbiad840_png.py \
  --src_root "$SRC_ROOT" \
  --out_root "$OUT_ROOT" \
  --align_start_hpf "$ALIGN_START_HPF" \
  --expect_t "$EXPECT_T" \
  --img_size "$IMG_SIZE" \
  --p_lo "$P_LO" \
  --p_hi "$P_HI" \
  --pad_to_expect "$PAD_TO_EXPECT" \
  --limit "$LIMIT"

echo "[DONE] Outputs written under: $OUT_ROOT"
