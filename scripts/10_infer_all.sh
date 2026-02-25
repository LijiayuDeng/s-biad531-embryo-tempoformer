#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .env

PY="python3 src/EmbryoTempoFormer.py"

AMP_FLAG="--no-amp";  [ "${AMP:-0}" = "1" ] && AMP_FLAG="--amp"
EMA_FLAG="--no-use_ema"; [ "${USE_EMA:-0}" = "1" ] && EMA_FLAG="--use_ema"

stamp="$(date +%Y%m%d_%H%M%S)"
OUTROOT="${RUNS_DIR:-./runs}/paper_eval_${stamp}"
mkdir -p "$OUTROOT"
echo "[INFO] OUTROOT=$OUTROOT"

models=(cnn_single meanpool nocons full)

ckpt_of () {
  case "$1" in
    cnn_single) echo "$CKPT_CNN_SINGLE" ;;
    meanpool) echo "$CKPT_MEANPOOL" ;;
    nocons) echo "$CKPT_NOCONS" ;;
    full) echo "$CKPT_FULL" ;;
  esac
}

infer_one () {
  local PROC="$1" EID="$2" OUT="$3" CKPT="$4"
  local IN="$PROC/$EID.npy"
  [ -f "$IN" ] || { echo "[WARN] missing $IN"; return; }
  [ -f "$OUT" ] && return
  $PY infer \
    --ckpt "$CKPT" \
    --input_path "$IN" \
    --out_json "$OUT" \
    --clip_len "${CLIP_LEN:-24}" \
    --img_size "${IMG_SIZE:-384}" \
    --expect_t "${EXPECT_T:-192}" \
    --stride "${STRIDE:-8}" \
    --trim 0.2 \
    --device "${DEVICE:-auto}" $AMP_FLAG $EMA_FLAG \
    --batch_size "${BATCH_SIZE:-64}" --num_workers 0 \
    --mem_profile lowmem \
    >/dev/null
}

# datasets: tag|proc|split|key
datasets=(
  "ID28C5_TEST|$PROC_28C5|$SPLIT_28C5|test"
  "EXT25C_TEST|$PROC_25C|$SPLIT_25C|test"
)

for ds in "${datasets[@]}"; do
  IFS="|" read -r TAG PROC SPLIT KEY <<<"$ds"
  for model in "${models[@]}"; do
    CKPT="$(ckpt_of "$model")"
    OUTDIR="$OUTROOT/$TAG/$model/json"
    mkdir -p "$OUTDIR"

    echo "[RUN] infer $TAG $model"
    while read -r eid; do
      [ -z "$eid" ] && continue
      infer_one "$PROC" "$eid" "$OUTDIR/$eid.json" "$CKPT"
    done < <(python3 - <<PY
import json
sp=json.load(open("$SPLIT","r"))
for eid in sp["$KEY"]:
    print(eid)
PY
)
  done
done

echo "[DONE] infer json in $OUTROOT"
echo "$OUTROOT" > "$OUTROOT/OUTROOT.txt"
