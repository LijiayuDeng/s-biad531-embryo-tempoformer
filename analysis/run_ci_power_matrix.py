#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from infer_utils import parse_csv_list


def run_checked(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run CI and power analysis across model matrix.")
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--csv_a_tag", default="EXT25C_TEST")
    ap.add_argument("--csv_b_tag", default="ID28C5_TEST")
    ap.add_argument("--label_a", default="25C")
    ap.add_argument("--label_b", default="28C5")
    ap.add_argument("--m_col", default="m_anchor")
    ap.add_argument("--ci_B", type=int, default=5000)
    ap.add_argument("--power_R", type=int, default=500)
    ap.add_argument("--power_B", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ci_script = root / "analysis" / "ci_delta_m.py"
    power_script = root / "analysis" / "power_curve.py"
    outroot = Path(args.outroot)
    if not outroot.is_dir():
        raise SystemExit(f"[ERR] OUTROOT not found: {outroot}")

    for model in parse_csv_list(args.models):
        a = outroot / args.csv_a_tag / model / "embryo.csv"
        b = outroot / args.csv_b_tag / model / "embryo.csv"
        if not a.exists():
            raise SystemExit(f"[ERR] missing {a}")
        if not b.exists():
            raise SystemExit(f"[ERR] missing {b}")

        print(f"== CI & POWER for {model} ==")
        run_checked(
            [
                sys.executable,
                str(ci_script),
                "--csv_a",
                str(a),
                "--csv_b",
                str(b),
                "--label_a",
                args.label_a,
                "--label_b",
                args.label_b,
                "--m_col",
                args.m_col,
                "--B",
                str(args.ci_B),
                "--seed",
                str(args.seed),
                "--out_json",
                str(outroot / f"CI_{model}_{args.m_col}.json"),
            ]
        )
        run_checked(
            [
                sys.executable,
                str(power_script),
                "--csv_a",
                str(a),
                "--csv_b",
                str(b),
                "--label_a",
                args.label_a,
                "--label_b",
                args.label_b,
                "--m_col",
                args.m_col,
                "--R",
                str(args.power_R),
                "--B",
                str(args.power_B),
                "--seed",
                str(args.seed),
                "--out_csv",
                str(outroot / f"power_{model}_{args.m_col}.csv"),
                "--out_png",
                str(outroot / f"power_{model}_{args.m_col}.png"),
            ]
        )


if __name__ == "__main__":
    main()
