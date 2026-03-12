#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from env_utils import resolve_path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Thin orchestration wrapper for summarize_sbiad840_transfer.py using explicit Princeton run/eval inputs."
        )
    )
    ap.add_argument("--out_dir", required=True)
    ap.add_argument(
        "--experiment",
        action="append",
        nargs=4,
        metavar=("LABEL", "RUN_DIR", "EVAL28_OUTROOT", "EVAL25_OUTROOT"),
        default=[],
        help="Experiment tuple passed through to summarize_sbiad840_transfer.py",
    )
    ap.add_argument("--out_csv", default="")
    ap.add_argument("--out_md", default="")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if not args.experiment:
        raise SystemExit(
            "No experiments provided. Pass one or more --experiment LABEL RUN_DIR EVAL28_OUTROOT EVAL25_OUTROOT tuples."
        )

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = Path(resolve_path(args.out_dir, repo_root))
    out_csv = resolve_path(args.out_csv, repo_root) if args.out_csv else str(out_dir / "sbiad840_finetune_compare.csv")
    out_md = resolve_path(args.out_md, repo_root) if args.out_md else str(out_dir / "sbiad840_finetune_compare.md")

    cmd = [sys.executable, "analysis/summarize_sbiad840_transfer.py"]
    for label, run_dir, eval28, eval25 in args.experiment:
        cmd.extend(
            [
                "--experiment",
                label,
                resolve_path(run_dir, repo_root),
                resolve_path(eval28, repo_root),
                resolve_path(eval25, repo_root),
            ]
        )
    cmd.extend(["--out_csv", out_csv, "--out_md", out_md])

    subprocess.run(cmd, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
