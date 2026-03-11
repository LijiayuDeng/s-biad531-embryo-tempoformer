#!/usr/bin/env python3
"""
Summarize clip-length sensitivity as a compact context ladder and linear fits.

Why two outputs:
1) `context_ladder.csv`
   Combines:
   - `cnn_single` from the main benchmark as the 0 h / single-frame reference
   - ETF-full from clip-length sensitivity runs at 1/3/6 h context

2) `full_context_fit.csv`
   Fits straight lines only within ETF-full across 1/3/6 h.
   We do NOT include the 0 h `cnn_single` point in these fits because it is a
   different model family (identity baseline rather than temporal transformer),
   and mixing architectures would confound context-length effects with model
   formulation differences.

This script is descriptive. It is intended to support reviewer response text,
not to replace the main benchmark tables.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, TypedDict, cast

import numpy as np


class GlobalMetricsPoints(TypedDict):
    mae: float
    rmse: float
    r2: float


class FitAnchorT0(TypedDict):
    m: float
    rmse_resid: float
    max_abs_resid: float


class SummaryJSON(TypedDict):
    global_metrics_points: GlobalMetricsPoints
    fit_anchor_T0: FitAnchorT0


JSONDict = dict[str, Any]
CSVRow = dict[str, str]
OutputRow = dict[str, object]
FloatPoint = dict[str, float]


def read_json(path: Path) -> JSONDict:
    with open(path, "r", encoding="utf-8") as f:
        return cast(JSONDict, json.load(f))


def read_csv(path: Path) -> list[CSVRow]:
    with open(path, "r", encoding="utf-8") as f:
        return cast(list[CSVRow], list(csv.DictReader(f)))


def write_csv(path: Path, rows: list[OutputRow], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main_outroot", required=True, help="main paper_eval outroot containing cnn_single summaries")
    ap.add_argument("--cliplen_csv", required=True, help="clip-length sensitivity summary csv")
    ap.add_argument("--out_dir", required=True, help="output directory")
    args = ap.parse_args()

    main_outroot = Path(args.main_outroot)
    cliplen_csv = Path(args.cliplen_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clip_rows = read_csv(cliplen_csv)

    ladder_rows: list[OutputRow] = []
    fit_rows: list[OutputRow] = []

    datasets = sorted({r["dataset"] for r in clip_rows})
    metrics = ["mae", "rmse", "r2", "rmse_resid", "max_abs_resid", "m_anchor_global"]

    for ds in datasets:
        # 0 h reference from cnn_single
        s = cast(SummaryJSON, read_json(main_outroot / ds / "cnn_single" / "summary.json"))
        gm = s["global_metrics_points"]
        fa = s["fit_anchor_T0"]
        ladder_rows.append(
            {
                "dataset": ds,
                "context_h": 0.0,
                "label": "cnn_single_0h",
                "model_family": "cnn_single",
                "clip_len": 1,
                "mae": gm["mae"],
                "rmse": gm["rmse"],
                "r2": gm["r2"],
                "rmse_resid": fa["rmse_resid"],
                "max_abs_resid": fa["max_abs_resid"],
                "m_anchor_global": fa["m"],
                "fit_note": "separate image-only baseline; not included in full-context linear fit",
            }
        )

        # ETF-full context ladder
        full_pts: list[FloatPoint] = []
        for L in (4, 12, 24):
            r = next(
                row
                for row in clip_rows
                if row["dataset"] == ds and row["model"] == "full" and int(row["clip_len"]) == L
            )
            context_h = float(L) * 0.25
            row_out: OutputRow = {
                "dataset": ds,
                "context_h": context_h,
                "label": f"full_L{L}",
                "model_family": "ETF-full",
                "clip_len": L,
                "fit_note": "included in full-context linear fit",
            }
            for m in metrics:
                row_out[m] = float(r[m])
            ladder_rows.append(row_out)

            fp: FloatPoint = {"context_h": context_h}
            for m in metrics:
                fp[m] = float(r[m])
            full_pts.append(fp)

        # Linear fits only across ETF-full 1/3/6 h contexts
        x = np.asarray([p["context_h"] for p in full_pts], dtype=np.float64)
        for m in metrics:
            y = np.asarray([p[m] for p in full_pts], dtype=np.float64)
            coef = np.polyfit(x, y, deg=1)
            y_hat = np.polyval(coef, x)
            sse = float(np.sum((y - y_hat) ** 2))
            sst = float(np.sum((y - float(np.mean(y))) ** 2))
            fit_r2 = float(1.0 - sse / sst) if sst > 1e-12 else float("nan")
            fit_rows.append(
                {
                    "dataset": ds,
                    "model_family": "ETF-full",
                    "metric": m,
                    "contexts_h": "1,3,6",
                    "n_points": int(len(x)),
                    "slope_per_hour": float(coef[0]),
                    "intercept": float(coef[1]),
                    "fit_r2": fit_r2,
                }
            )

    ladder_fields = [
        "dataset",
        "context_h",
        "label",
        "model_family",
        "clip_len",
        "mae",
        "rmse",
        "r2",
        "rmse_resid",
        "max_abs_resid",
        "m_anchor_global",
        "fit_note",
    ]
    fit_fields = [
        "dataset",
        "model_family",
        "metric",
        "contexts_h",
        "n_points",
        "slope_per_hour",
        "intercept",
        "fit_r2",
    ]

    write_csv(out_dir / "context_ladder.csv", ladder_rows, ladder_fields)
    write_csv(out_dir / "full_context_fit.csv", fit_rows, fit_fields)
    print("WROTE:", out_dir / "context_ladder.csv")
    print("WROTE:", out_dir / "full_context_fit.csv")


if __name__ == "__main__":
    main()
