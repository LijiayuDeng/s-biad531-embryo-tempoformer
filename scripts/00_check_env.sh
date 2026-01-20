#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f ".env" ]; then
  echo "[ERR] .env not found. Run: cp .env.example .env  and edit paths."
  exit 1
fi

source .env

req_vars=(
  PROC_28C5 PROC_25C SPLIT_28C5 SPLIT_25C
  CKPT_CNN_SINGLE CKPT_MEANPOOL CKPT_NOCONS CKPT_FULL
)

for v in "${req_vars[@]}"; do
  if [ -z "${!v:-}" ]; then
    echo "[ERR] missing env var: $v"
    exit 1
  fi
done

echo "== check paths =="
ls -ld "$PROC_28C5" "$PROC_25C" "$SPLIT_28C5" "$SPLIT_25C" >/dev/null
ls -lh "$CKPT_CNN_SINGLE" "$CKPT_MEANPOOL" "$CKPT_NOCONS" "$CKPT_FULL" >/dev/null

echo "[OK] env + paths look good"
