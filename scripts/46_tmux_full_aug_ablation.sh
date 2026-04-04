#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/_shell_env.sh

if [ -f ".env" ]; then
  load_repo_env_if_present ".env"
else
  echo "[ERR] .env not found. Run: cp .env.example .env and edit paths."
  exit 1
fi

SESSION="${1:-etf_full_aug}"
OUTROOT="${2:-${OUTROOT:-${RUNS_DIR:-./runs}/aug_ablation_full_$(date +%Y%m%d_%H%M%S)}}"

mkdir -p "$OUTROOT/logs"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[ERR] tmux session already exists: $SESSION"
  exit 1
fi

CMD="cd '$PWD' && bash scripts/45_train_full_aug_ablation.sh '$OUTROOT' 2>&1 | tee '$OUTROOT/logs/session.log'"
tmux new-session -d -s "$SESSION" "$CMD"

echo "[OK] tmux session started: $SESSION"
echo "[OK] OUTROOT: $OUTROOT"
echo "[OK] attach: tmux attach -t $SESSION"
echo "[OK] live log: tail -f '$OUTROOT/logs/session.log'"
echo "[OK] stop session: tmux kill-session -t $SESSION"
