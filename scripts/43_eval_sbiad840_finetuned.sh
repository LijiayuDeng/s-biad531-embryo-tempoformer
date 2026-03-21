#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source scripts/_shell_env.sh
load_repo_env_if_present ".env"
OUTROOT="${1:-${OUTROOT:-./runs/sbiad840_finetuned_eval}}"
DATASETS="${DATASETS:-SBIAD840_28C5_TEST,SBIAD840_25C_TEST}"
DEVICE="${DEVICE:-cuda}"
AMP="${AMP:-1}"
USE_EMA="${USE_EMA:-1}"
BATCH_SIZE="${BATCH_SIZE:-64}"
CLIP_LEN="${CLIP_LEN:-24}"
IMG_SIZE="${IMG_SIZE:-384}"
EXPECT_T="${EXPECT_T:-192}"
STRIDE="${STRIDE:-8}"
DT_H="${DT_H:-0.25}"
T0_HPF="${T0_HPF:-4.5}"
OUT_CSV="${OUT_CSV:-$OUTROOT/sbiad840_external_summary.csv}"
OUT_MD="${OUT_MD:-$OUTROOT/sbiad840_external_summary.md}"

FT_CKPT="${FT_CKPT:-}"
MODEL="${MODEL:-}"
PROC_28C5_SBIAD840="${PROC_28C5_SBIAD840:-}"
PROC_25C_SBIAD840="${PROC_25C_SBIAD840:-}"
SPLIT_28C5_SBIAD840="${SPLIT_28C5_SBIAD840:-}"
SPLIT_25C_SBIAD840="${SPLIT_25C_SBIAD840:-}"

if [[ -z "$FT_CKPT" || -z "$MODEL" ]]; then
  echo "[ERR] Set FT_CKPT and MODEL"
  exit 1
fi

cmd=(
  "$PYTHON_BIN" analysis/eval_sbiad840_finetuned.py
  --ft_ckpt "$FT_CKPT"
  --model "$MODEL"
  --outroot "$OUTROOT"
  --datasets "$DATASETS"
  --device "$DEVICE"
  --amp "$AMP"
  --use_ema "$USE_EMA"
  --force_infer "${FORCE_INFER:-1}"
  --batch_size "$BATCH_SIZE"
  --clip_len "$CLIP_LEN"
  --img_size "$IMG_SIZE"
  --expect_t "$EXPECT_T"
  --stride "$STRIDE"
  --dt "$DT_H"
  --t0 "$T0_HPF"
  --out_csv "$OUT_CSV"
  --out_md "$OUT_MD"
)

[[ -n "$PROC_28C5_SBIAD840" ]] && cmd+=(--proc_28c5_sbiad840 "$PROC_28C5_SBIAD840")
[[ -n "$PROC_25C_SBIAD840" ]] && cmd+=(--proc_25c_sbiad840 "$PROC_25C_SBIAD840")
[[ -n "$SPLIT_28C5_SBIAD840" ]] && cmd+=(--split_28c5_sbiad840 "$SPLIT_28C5_SBIAD840")
[[ -n "$SPLIT_25C_SBIAD840" ]] && cmd+=(--split_25c_sbiad840 "$SPLIT_25C_SBIAD840")

"${cmd[@]}"

echo "[DONE] Fine-tuned S-BIAD840 evaluation written under: $OUTROOT"
