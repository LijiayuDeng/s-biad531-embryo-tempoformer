#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def read_points_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    xs: list[float] = []
    ys: list[float] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            xs.append(float(row["x_true"]))
            ys.append(float(row["y_pred"]))
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def read_t0_finals(json_dir: Path) -> np.ndarray:
    vals: list[float] = []
    for fp in sorted(json_dir.glob("*.json")):
        obj = json.loads(fp.read_text())
        vals.append(float(obj["t0_final"]))
    return np.asarray(vals, dtype=np.float64)


def origin_fit_stats(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    denom = float(np.dot(x, x))
    m_origin = float(np.dot(x, y) / denom) if denom > 0 else float("nan")
    resid = y - m_origin * x
    corr = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else float("nan")
    return {
        "m_origin": m_origin,
        "origin_resid_mean": float(np.mean(resid)),
        "origin_resid_sd": float(np.std(resid, ddof=0)),
        "origin_resid_rmse": float(np.sqrt(np.mean(np.square(resid)))),
        "corr_r2": corr * corr,
    }


def fmt(v: Any, digits: int = 3) -> str:
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    try:
        x = float(v)
    except Exception:
        return str(v)
    if np.isnan(x):
        return "nan"
    return f"{x:.{digits}f}"


def rows_to_markdown(rows: Iterable[dict[str, Any]], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize completed S-BIAD840 external-domain ETF evaluation."
    )
    ap.add_argument("--outroot", required=True)
    ap.add_argument(
        "--datasets",
        default="SBIAD840_28C5_TEST,SBIAD840_25C_TEST",
        help="Comma-separated external datasets to summarize.",
    )
    ap.add_argument(
        "--models",
        default="cnn_single,meanpool,nocons,full",
        help="Comma-separated models to summarize.",
    )
    ap.add_argument("--out_csv", default="")
    ap.add_argument("--out_md", default="")
    args = ap.parse_args()

    outroot = Path(args.outroot)
    datasets = [x for x in args.datasets.split(",") if x]
    models = [x for x in args.models.split(",") if x]
    out_csv = Path(args.out_csv) if args.out_csv else outroot / "sbiad840_external_summary.csv"
    out_md = Path(args.out_md) if args.out_md else outroot / "sbiad840_external_summary.md"

    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for model in models:
            model_dir = outroot / dataset / model
            summary_fp = model_dir / "summary.json"
            points_fp = model_dir / "points.csv"
            json_dir = model_dir / "json"
            if not (summary_fp.exists() and points_fp.exists() and json_dir.exists()):
                continue

            summary = json.loads(summary_fp.read_text())
            gm = summary["global_metrics_points"]
            fa = summary["fit_anchor_T0"]
            x_true, y_pred = read_points_csv(points_fp)
            t0_final = read_t0_finals(json_dir)
            ofs = origin_fit_stats(x_true, y_pred)

            rows.append(
                {
                    "dataset": dataset,
                    "model": model,
                    "n_json": int(len(t0_final)),
                    "n_points": int(len(x_true)),
                    "mae_h": float(gm["mae"]),
                    "rmse_h": float(gm["rmse"]),
                    "r2_points": float(gm["r2"]),
                    "m_anchor": float(fa["m"]),
                    "rmse_resid_h": float(fa["rmse_resid"]),
                    "max_abs_resid_h": float(fa["max_abs_resid"]),
                    "t0_final_mean_h": float(np.mean(t0_final)),
                    "t0_final_median_h": float(np.median(t0_final)),
                    "t0_final_sd_h": float(np.std(t0_final, ddof=0)),
                    "m_origin": ofs["m_origin"],
                    "origin_resid_mean_h": ofs["origin_resid_mean"],
                    "origin_resid_sd_h": ofs["origin_resid_sd"],
                    "origin_resid_rmse_h": ofs["origin_resid_rmse"],
                    "corr_r2": ofs["corr_r2"],
                }
            )

    if not rows:
        raise SystemExit("No completed external summaries found.")

    fieldnames = list(rows[0].keys())
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    pretty_rows: list[dict[str, str]] = []
    for row in rows:
        pretty_rows.append(
            {
                "dataset": row["dataset"],
                "model": row["model"],
                "RMSE (h)": fmt(row["rmse_h"]),
                "R2": fmt(row["r2_points"]),
                "m_anchor": fmt(row["m_anchor"]),
                "rmse_resid (h)": fmt(row["rmse_resid_h"]),
                "t0 median (h)": fmt(row["t0_final_median_h"]),
                "m_origin": fmt(row["m_origin"]),
                "origin resid mean±sd (h)": f"{fmt(row['origin_resid_mean_h'])} ± {fmt(row['origin_resid_sd_h'])}",
                "corr^2": fmt(row["corr_r2"]),
            }
        )

    headers = [
        "dataset",
        "model",
        "RMSE (h)",
        "R2",
        "m_anchor",
        "rmse_resid (h)",
        "t0 median (h)",
        "m_origin",
        "origin resid mean±sd (h)",
        "corr^2",
    ]
    out_md.write_text(rows_to_markdown(pretty_rows, headers))

    print(f"WROTE: {out_csv}")
    print(f"WROTE: {out_md}")


if __name__ == "__main__":
    main()
