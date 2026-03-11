#!/usr/bin/env python3
"""
Summarize T0 anchor sensitivity outputs produced by repeated aggregation runs.

Expected directory layout:
  <outdir>/
    t0_4p0/ID28C5_TEST/full/summary.json
    t0_4p5/...
    t0_5p0/...

This script does not retrain models. It only summarizes analysis-time
re-aggregation under alternative anchors.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_csv_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--out_csv", default="")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    datasets = parse_csv_list(args.datasets)
    models = parse_csv_list(args.models)

    rows: list[dict[str, object]] = []
    for tdir in sorted(outdir.iterdir()):
        if not tdir.is_dir() or not tdir.name.startswith("t0_"):
            continue
        t0 = float(tdir.name.split("_", 1)[1].replace("p", "."))
        for ds in datasets:
            for model in models:
                summary_path = tdir / ds / model / "summary.json"
                if not summary_path.exists():
                    raise FileNotFoundError(summary_path)
                summary = load_json(summary_path)
                gm = summary["global_metrics_points"]
                fa = summary["fit_anchor_T0"]
                rows.append(
                    {
                        "t0_hpf": t0,
                        "dataset": ds,
                        "model": model,
                        "mae": gm["mae"],
                        "rmse": gm["rmse"],
                        "r2": gm["r2"],
                        "m_anchor_global": fa["m"],
                        "rmse_resid": fa["rmse_resid"],
                        "max_abs_resid": fa["max_abs_resid"],
                    }
                )

    if not rows:
        raise RuntimeError(f"No t0_* subdirectories found under {outdir}")

    rows.sort(key=lambda r: (str(r["dataset"]), str(r["model"]), float(r["t0_hpf"])))
    out_csv = Path(args.out_csv) if args.out_csv else (outdir / "anchor_sensitivity_summary.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"WROTE: {out_csv}")


if __name__ == "__main__":
    main()
