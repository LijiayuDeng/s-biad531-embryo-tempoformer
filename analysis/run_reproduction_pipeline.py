#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def run_checked(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, check=True, cwd=str(cwd))


def env_flag(name: str, default: int) -> bool:
    return os.environ.get(name, str(default)) == "1"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full ETF reproduction pipeline.")
    ap.add_argument("--outroot", default=os.environ.get("OUTROOT", ""))
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    outroot = args.outroot.strip()
    if not outroot:
        runs_dir = os.environ.get("RUNS_DIR", "./runs")
        outroot = str(Path(runs_dir) / f"paper_eval_{time.strftime('%Y%m%d_%H%M%S')}")

    print(f"[INFO] target OUTROOT={outroot}")
    run_checked(["bash", str(scripts / "00_check_env.sh")], root)
    run_checked(["bash", str(scripts / "10_infer_all.sh"), outroot], root)
    run_checked(["bash", str(scripts / "20_aggregate_all.sh"), outroot], root)

    if env_flag("RUN_STAGE_ERROR_BINS", 1):
        run_checked(
            ["bash", str(scripts / "32_stage_error_bins.sh"), outroot, f"{outroot}/stage_error/stage_error_by_bin.csv"],
            root,
        )
    if env_flag("RUN_ANCHOR_SENSITIVITY", 1):
        run_checked(["bash", str(scripts / "33_anchor_sensitivity.sh"), outroot, f"{outroot}/anchor_sensitivity"], root)

    run_checked(["bash", str(scripts / "30_ci_power_all.sh"), outroot], root)

    if env_flag("RUN_CONTINUOUS_POWER", 1):
        run_checked(["bash", str(scripts / "31_power_curve_continuous.sh"), outroot, f"{outroot}/continuous_power"], root)

    if env_flag("RUN_CLIPLEN_SENSITIVITY", 1):
        cliplen_outroot = os.environ.get("CLIPLEN_OUTROOT", f"{outroot}/cliplen_sensitivity")
        run_checked(["bash", str(scripts / "11_cliplen_sensitivity.sh"), cliplen_outroot], root)
        run_checked(
            ["bash", str(scripts / "12_cliplen_context_fit.sh"), outroot, cliplen_outroot, f"{cliplen_outroot}/context_fit"],
            root,
        )

    run_checked(["bash", str(scripts / "40_make_figures.sh"), outroot], root)

    if env_flag("RUN_SALIENCY", 0):
        sal_model = os.environ.get("SALIENCY_MODEL", "full")
        run_checked(["bash", str(scripts / "50_saliency_best_id28c5.sh"), outroot, sal_model], root)

    print(f"[DONE] All outputs under: {outroot}")


if __name__ == "__main__":
    main()
