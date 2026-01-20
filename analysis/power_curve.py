#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmbryoTempoFormer — Sample efficiency (power curve)
===================================================

We quantify sample efficiency as a power curve:
  E embryos per condition  ->  probability of detecting Δm != 0

Definition
----------
- For each embryo budget E:
  - Repeat R simulated experiments.
  - In each experiment:
    - Sample E embryos from condition A and E embryos from condition B.
    - Compute Δ = mean(m_A) - mean(m_B).
    - Compute a 95% CI for Δ using embryo-bootstrap with B replicates
      (bootstrap resampling within the sampled embryos).
    - Declare "success" if CI excludes 0 (i.e., lo>0 or hi<0).
- power(E) = success_rate over R experiments.

Inputs
------
Two embryo.csv files (one per condition), produced by the evaluation pipeline.
The tempo column defaults to `m_anchor` (anchored at 4.5 hpf).

Outputs
-------
- CSV: E, power, delta_mean, ci_mean_low, ci_mean_high, nA, nB, R, B, seed, replacement
- PNG: optional power curve plot (requires matplotlib)

Notes
-----
- This is embryo-level inference, avoiding pseudo-replication among time-lapse windows.
- Use --replacement to sample embryos with replacement at the experiment level
  (default is without replacement, mimicking a real experimental budget).

Example
-------
python analysis/power_curve.py \
  --csv_a runs/.../EXT25C_TEST/full/embryo.csv \
  --csv_b runs/.../ID28C5_TEST/full/embryo.csv \
  --out_csv runs/.../power_full.csv \
  --out_png runs/.../power_full.png \
  --E_list 2,4,6,8,10,12,14,16,18,20 \
  --R 1000 --B 1000 --seed 0
"""

from __future__ import annotations
import argparse, csv, json, math, os
from typing import List, Dict, Tuple
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

def bootstrap_ci_delta(mA: np.ndarray, mB: np.ndarray, B: int, rng: np.random.Generator) -> Tuple[float, float]:
    """
    Compute 95% CI for Δ = mean(mA)-mean(mB) by bootstrapping embryos *within*
    the sampled set.
    Vectorized for speed.
    """
    nA, nB = mA.size, mB.size
    ia = rng.integers(0, nA, size=(B, nA))
    ib = rng.integers(0, nB, size=(B, nB))
    d = mA[ia].mean(axis=1) - mB[ib].mean(axis=1)
    lo = float(np.quantile(d, 0.025))
    hi = float(np.quantile(d, 0.975))
    return lo, hi

def parse_E_list(s: str) -> List[int]:
    xs=[]
    for part in s.split(","):
        part=part.strip()
        if not part:
            continue
        xs.append(int(part))
    xs=sorted(set(xs))
    return xs

def default_E_list(nmin: int) -> List[int]:
    hi = min(30, nmin)
    xs = list(range(2, hi+1, 2))
    if hi >= 3 and 3 not in xs:
        xs.insert(0, 3)  # optional
    xs = sorted(set([x for x in xs if x <= nmin and x >= 2]))
    return xs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv_a", required=True, help="embryo.csv for condition A (e.g., 25C)")
    ap.add_argument("--csv_b", required=True, help="embryo.csv for condition B (e.g., 28C5)")
    ap.add_argument("--m_col", default="m_anchor")
    ap.add_argument("--E_list", default="", help="comma-separated list, e.g. 2,4,6,...; empty=auto")
    ap.add_argument("--R", type=int, default=1000, help="outer repeats (experiments)")
    ap.add_argument("--B", type=int, default=1000, help="inner bootstrap replicates per experiment")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--replacement", action="store_true", help="sample embryos with replacement at the experiment level")
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--out_png", default="")
    ap.add_argument("--label_a", default="A")
    ap.add_argument("--label_b", default="B")
    args = ap.parse_args()

    A = read_col(args.csv_a, args.m_col)
    B = read_col(args.csv_b, args.m_col)
    nA, nB = A.size, B.size
    nmin = min(nA, nB)

    E_list = parse_E_list(args.E_list) if args.E_list else default_E_list(nmin)
    if not E_list:
        raise ValueError("E_list is empty after parsing.")
    if max(E_list) > nmin:
        raise ValueError(f"Max E={max(E_list)} exceeds available embryos nmin={nmin}")

    rng = np.random.default_rng(args.seed)

    rows=[]
    for E in E_list:
        succ=0
        deltas=[]
        los=[]
        his=[]

        for _ in range(args.R):
            if args.replacement:
                idxA = rng.integers(0, nA, size=E)
                idxB = rng.integers(0, nB, size=E)
            else:
                idxA = rng.choice(nA, size=E, replace=False)
                idxB = rng.choice(nB, size=E, replace=False)

            mA = A[idxA]
            mB = B[idxB]
            delta = float(mA.mean() - mB.mean())

            lo, hi = bootstrap_ci_delta(mA, mB, args.B, rng)

            ok = (lo > 0.0) or (hi < 0.0)
            succ += int(ok)
            deltas.append(delta); los.append(lo); his.append(hi)

        power = succ / float(args.R)
        rows.append({
            "E": int(E),
            "power": float(power),
            "delta_mean": float(np.mean(deltas)),
            "ci_low_mean": float(np.mean(los)),
            "ci_high_mean": float(np.mean(his)),
            "nA": int(nA),
            "nB": int(nB),
            "R": int(args.R),
            "B": int(args.B),
            "seed": int(args.seed),
            "replacement": bool(args.replacement),
            "label_a": args.label_a,
            "label_b": args.label_b,
        })
        print(f"E={E:>2d} power={power:.3f} (nA={nA} nB={nB})")

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print("WROTE:", args.out_csv)

    # Optional plot
    if args.out_png:
        try:
            import matplotlib.pyplot as plt
            xs=[r["E"] for r in rows]
            ys=[r["power"] for r in rows]
            plt.figure(figsize=(6.2,4.0))
            plt.plot(xs, ys, marker="o")
            plt.ylim(-0.02, 1.02)
            plt.xlabel("E embryos per condition")
            plt.ylabel("Power (CI excludes 0)")
            plt.title(f"Power curve: {args.label_a} vs {args.label_b} ({args.m_col})")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(args.out_png, dpi=200)
            print("WROTE:", args.out_png)
        except Exception as e:
            print("[WARN] plot skipped:", repr(e))

if __name__ == "__main__":
    main()
