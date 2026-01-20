#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmbryoTempoFormer — Confidence Intervals for tempo differences (Δm)
===================================================================

This script computes embryo-bootstrap confidence intervals for the difference
in tempo slope m between two conditions (e.g., 25°C vs 28.5°C).

Inputs
------
Two CSV files produced by the evaluation pipeline:
  - embryo.csv for condition A (e.g., 25°C)
  - embryo.csv for condition B (e.g., 28.5°C)

Each embryo.csv must contain a column `m_anchor` (default) or another column
you specify via --m_col.

Important statistical note
--------------------------
Time-lapse window predictions are correlated within embryo. Therefore, the embryo
is the correct statistical unit. This script bootstraps embryos (not windows).

Output
------
A JSON file with:
  - observed Δm
  - 95% CI via bootstrap percentiles
  - group summaries (mean/median/p05/p95, n)

Example
-------
python analysis/ci_delta_m.py \
  --csv_a runs/paper_eval_xxx/EXT25C_TEST/full/embryo.csv \
  --csv_b runs/paper_eval_xxx/ID28C5_TEST/full/embryo.csv \
  --out_json runs/paper_eval_xxx/ci_full_anchor.json \
  --B 5000 --seed 0
"""

from __future__ import annotations
import argparse, csv, json, math, os
from typing import List, Tuple, Dict
import numpy as np

def read_col(csv_path: str, col: str) -> np.ndarray:
    vals: List[float] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if col not in r.fieldnames:
            raise ValueError(f"Column '{col}' not found in {csv_path}. fields={r.fieldnames}")
        for row in r:
            try:
                v = float(row[col])
            except Exception:
                continue
            if math.isfinite(v):
                vals.append(v)
    if len(vals) == 0:
        raise ValueError(f"No finite values for column '{col}' in {csv_path}")
    return np.array(vals, dtype=np.float64)

def summarize(x: np.ndarray) -> Dict[str, float]:
    x = np.asarray(x, dtype=np.float64)
    return {
        "n": int(x.size),
        "mean": float(x.mean()),
        "median": float(np.median(x)),
        "p05": float(np.quantile(x, 0.05)),
        "p95": float(np.quantile(x, 0.95)),
        "std": float(x.std(ddof=1)) if x.size > 1 else float("nan"),
    }

def bootstrap_delta(a: np.ndarray, b: np.ndarray, B: int, seed: int) -> Tuple[float, float, float, np.ndarray]:
    """
    Bootstrap Δ = mean(a) - mean(b) by resampling embryos with replacement.
    Returns: (delta_obs, ci_low, ci_high, samples)
    """
    rng = np.random.default_rng(seed)
    na, nb = a.size, b.size
    delta_obs = float(a.mean() - b.mean())

    ia = rng.integers(0, na, size=(B, na))
    ib = rng.integers(0, nb, size=(B, nb))
    ma = a[ia].mean(axis=1)
    mb = b[ib].mean(axis=1)
    d = ma - mb
    lo = float(np.quantile(d, 0.025))
    hi = float(np.quantile(d, 0.975))
    return delta_obs, lo, hi, d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv_a", required=True, help="embryo.csv for condition A (e.g., 25C)")
    ap.add_argument("--csv_b", required=True, help="embryo.csv for condition B (e.g., 28C5)")
    ap.add_argument("--m_col", default="m_anchor", help="column name to use as tempo slope")
    ap.add_argument("--B", type=int, default=5000, help="bootstrap replicates")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--label_a", default="A")
    ap.add_argument("--label_b", default="B")
    args = ap.parse_args()

    a = read_col(args.csv_a, args.m_col)
    b = read_col(args.csv_b, args.m_col)

    delta_obs, lo, hi, samples = bootstrap_delta(a, b, args.B, args.seed)

    out = {
        "meta": {
            "csv_a": os.path.abspath(args.csv_a),
            "csv_b": os.path.abspath(args.csv_b),
            "label_a": args.label_a,
            "label_b": args.label_b,
            "m_col": args.m_col,
            "B": int(args.B),
            "seed": int(args.seed),
            "definition": "Δ = mean(m_a) - mean(m_b)",
        },
        "group_a": summarize(a),
        "group_b": summarize(b),
        "delta": {
            "delta_obs": float(delta_obs),
            "ci95_low": float(lo),
            "ci95_high": float(hi),
        },
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("WROTE:", args.out_json)
    print("Δm =", out["delta"]["delta_obs"], "CI95=[", out["delta"]["ci95_low"], ",", out["delta"]["ci95_high"], "]")
    print("n_a =", out["group_a"]["n"], "n_b =", out["group_b"]["n"])

if __name__ == "__main__":
    main()
