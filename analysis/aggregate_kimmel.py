#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregate per-embryo infer JSONs into:
  - points.csv  : all (embryo, start) points
  - embryo.csv  : per-embryo anchored slope m + residual stats
  - summary.json: global metrics + global anchored fit

This script is designed for EmbryoTempoFormer infer outputs that contain:
  - starts  : list[int]
  - t0_hats : list[float]
Optional fields like t0_final/metrics may be NaN; we ignore them.

Definitions
----------
Let DT be the sampling interval in hours (default 0.25), and T0 be start time (default 4.5 hpf).

For each window start s:
  x = T0 + DT * s
  y = t0_hat(s) + DT * s          (predicted developmental time in hpf)

Anchored Kimmel-style fit (from T0):
  y - T0 = m * (x - T0)

Per-embryo m is fitted within each embryo.
Global m is fitted across all points pooled.

Outputs
-------
out_dir/
  points.csv
  embryo.csv
  summary.json

No pandas required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def load_json_allow_nan(path: Path) -> dict:
    # Python json can parse NaN/Infinity (non-standard) by default; keep it simple.
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fit_anchor_T0(x: np.ndarray, y: np.ndarray, T0: float) -> Tuple[float, np.ndarray]:
    """
    Fit (y - T0) = m * (x - T0) through origin in the anchored coordinates.
    Returns:
      m
      resid = (y - T0) - m*(x - T0)
    """
    xp = x - T0
    yp = y - T0
    msk = np.abs(xp) > 1e-12
    xp2 = xp[msk]
    yp2 = yp[msk]
    if xp2.size < 2:
        return float("nan"), np.full_like(yp, np.nan, dtype=np.float64)
    denom = float(np.sum(xp2 * xp2))
    if denom <= 1e-12:
        return float("nan"), np.full_like(yp, np.nan, dtype=np.float64)
    m = float(np.sum(xp2 * yp2) / denom)
    resid = yp - m * xp
    return m, resid


def rmse(a: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(a * a)))


def summarize_vec(x: np.ndarray) -> Dict[str, float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return dict(n=0, mean=float("nan"), median=float("nan"), p05=float("nan"), p95=float("nan"), std=float("nan"))
    return dict(
        n=int(x.size),
        mean=float(np.mean(x)),
        median=float(np.median(x)),
        p05=float(np.quantile(x, 0.05)),
        p95=float(np.quantile(x, 0.95)),
        std=float(np.std(x, ddof=1)) if x.size > 1 else float("nan"),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json_dir", required=True, help="directory containing per-embryo infer json files")
    ap.add_argument("--out_dir", required=True, help="output directory")
    ap.add_argument("--dt", type=float, default=0.25, help="sampling interval in hours")
    ap.add_argument("--t0", type=float, default=4.5, help="start time in hours post fertilization")
    args = ap.parse_args()

    json_dir = Path(args.json_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    DT = float(args.dt)
    T0 = float(args.t0)

    files = sorted(json_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No json files under: {json_dir}")

    # Collect rows
    point_rows: List[Tuple[str, int, float, float, float]] = []  # eid, start, x_true, y_pred, err(y-x)
    embryo_rows: List[Tuple[str, int, float, float, float]] = []  # eid, n_points, m_anchor, rmse_resid, max_abs_resid

    for fp in files:
        eid = fp.stem
        d = load_json_allow_nan(fp)

        starts = d.get("starts", [])
        t0_hats = d.get("t0_hats", [])
        if not isinstance(starts, list) or not isinstance(t0_hats, list) or len(starts) != len(t0_hats):
            # skip malformed
            continue

        # filter finite
        s_list = []
        t0_list = []
        for s, t0h in zip(starts, t0_hats):
            try:
                s_int = int(s)
                t0f = float(t0h)
            except Exception:
                continue
            if math.isfinite(t0f):
                s_list.append(s_int)
                t0_list.append(t0f)

        if len(s_list) < 2:
            continue

        s_arr = np.array(s_list, dtype=np.float64)
        t0_arr = np.array(t0_list, dtype=np.float64)

        x = T0 + DT * s_arr
        y = t0_arr + DT * s_arr
        err = y - x

        for s_int, xx, yy, ee in zip(s_list, x.tolist(), y.tolist(), err.tolist()):
            point_rows.append((eid, int(s_int), float(xx), float(yy), float(ee)))

        m, resid = fit_anchor_T0(x, y, T0=T0)
        rr = rmse(resid)
        max_abs = float(np.nanmax(np.abs(resid))) if np.isfinite(resid).any() else float("nan")
        embryo_rows.append((eid, int(len(s_list)), float(m), float(rr), float(max_abs)))

    if not point_rows:
        raise RuntimeError("No valid points aggregated. Check json format.")

    # Write points.csv
    points_path = out_dir / "points.csv"
    with open(points_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["eid", "start", "x_true", "y_pred", "err", "abs_err", "sq_err"])
        for eid, s, x_true, y_pred, err in point_rows:
            w.writerow([eid, s, x_true, y_pred, err, abs(err), err * err])

    # Write embryo.csv
    embryo_path = out_dir / "embryo.csv"
    with open(embryo_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["eid", "n_points", "m_anchor", "rmse_resid", "max_abs_resid"])
        for row in embryo_rows:
            w.writerow(list(row))

    # Global metrics over all points
    x_true = np.array([r[2] for r in point_rows], dtype=np.float64)
    y_pred = np.array([r[3] for r in point_rows], dtype=np.float64)
    err = y_pred - x_true

    mae = float(np.mean(np.abs(err)))
    rmse_pt = float(np.sqrt(np.mean(err * err)))

    sse = float(np.sum((y_pred - x_true) ** 2))
    sst = float(np.sum((x_true - float(np.mean(x_true))) ** 2))
    r2 = float(1.0 - sse / sst) if sst > 1e-12 else float("nan")

    # Global anchored fit
    m_g, resid_g = fit_anchor_T0(x_true, y_pred, T0=T0)
    rmse_resid_g = rmse(resid_g)
    max_abs_resid_g = float(np.nanmax(np.abs(resid_g))) if np.isfinite(resid_g).any() else float("nan")

    m_vals = np.array([r[2] for r in embryo_rows], dtype=np.float64)
    m_summary = summarize_vec(m_vals)

    summary = {
        "meta": {
            "dt_h": DT,
            "t0_hpf": T0,
            "json_dir": str(json_dir),
            "n_json": int(len(files)),
        },
        "global_metrics_points": {
            "n_points": int(len(point_rows)),
            "n_embryos": int(len(set(r[0] for r in point_rows))),
            "mae": mae,
            "rmse": rmse_pt,
            "r2": r2,
        },
        "fit_anchor_T0": {
            "definition": "fit (y - T0) = m * (x - T0)",
            "m": float(m_g),
            "rmse_resid": float(rmse_resid_g),
            "max_abs_resid": float(max_abs_resid_g),
        },
        "per_embryo_summary": {
            "m_mean": m_summary["mean"],
            "m_median": m_summary["median"],
            "m_p05": m_summary["p05"],
            "m_p95": m_summary["p95"],
        },
    }

    summary_path = out_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("WROTE:", points_path)
    print("WROTE:", embryo_path)
    print("WROTE:", summary_path)


if __name__ == "__main__":
    main()
