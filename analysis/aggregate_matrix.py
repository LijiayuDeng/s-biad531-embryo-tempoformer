#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from infer_utils import parse_csv_list


def count_json(json_dir: Path) -> int:
    return len(list(json_dir.glob("*.json")))


def aggregate_one(cli_script: Path, json_dir: Path, out_dir: Path, dt: float, t0: float) -> None:
    cmd = [
        sys.executable,
        str(cli_script),
        "--json_dir",
        str(json_dir),
        "--out_dir",
        str(out_dir),
        "--dt",
        str(dt),
        "--t0",
        str(t0),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate per-embryo inference JSONs across dataset/model matrix.")
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--dt", type=float, default=0.25)
    ap.add_argument("--t0", type=float, default=4.5)
    ap.add_argument("--force", type=int, default=0)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    cli_script = root / "analysis" / "aggregate_kimmel.py"
    outroot = Path(args.outroot)
    if not outroot.is_dir():
        raise SystemExit(f"[ERR] OUTROOT not found: {outroot}")

    for ds in parse_csv_list(args.datasets):
        for model in parse_csv_list(args.models):
            json_dir = outroot / ds / model / "json"
            out_dir = outroot / ds / model
            summary_json = out_dir / "summary.json"

            if not json_dir.is_dir():
                print(f"[WARN] missing json_dir: {json_dir} (skip)")
                continue
            njson = count_json(json_dir)
            if njson == 0:
                print(f"[WARN] no json files in: {json_dir} (skip)")
                continue
            if not args.force and summary_json.exists():
                print(f"[SKIP] {ds}/{model} already aggregated")
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"[AGG] {ds} / {model} (json={njson})")
            aggregate_one(cli_script, json_dir, out_dir, args.dt, args.t0)

    print(f"[DONE] Aggregation complete under: {outroot}")


if __name__ == "__main__":
    main()
