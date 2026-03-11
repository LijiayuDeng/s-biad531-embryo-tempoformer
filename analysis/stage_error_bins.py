#!/usr/bin/env python3
"""
Stage-stratified point-level error summary from aggregated `points.csv`.

Purpose
-------
Quantify where prediction errors arise along the nominal developmental timeline.
By default, bins follow broad Kimmel periods and are applied to the nominal
clip *start* time (`x_true`) produced by `analysis/aggregate_kimmel.py`.

This is descriptive only. Statistical claims should remain embryo-level.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


KIMMEL_PERIODS: list[tuple[str, float, float]] = [
    ("blastula", 2.25, 5.25),
    ("gastrula", 5.25, 10.33),
    ("segmentation", 10.33, 24.0),
    ("pharyngula", 24.0, 48.0),
    ("hatching", 48.0, 72.0),
]


def parse_csv_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def parse_bins(s: str) -> list[float]:
    vals = [float(x.strip()) for x in s.split(",") if x.strip()]
    if len(vals) < 2:
        raise ValueError("Need at least two bin edges")
    if any(b <= a for a, b in zip(vals[:-1], vals[1:])):
        raise ValueError("Bin edges must be strictly increasing")
    return vals


def build_fixed_bins(edges: list[float]) -> list[dict[str, object]]:
    return [
        {
            "stage_name": f"fixed_{i + 1}",
            "stage_label": f"{edges[i]:.1f}-{edges[i + 1]:.1f}",
            "canonical_lo_hpf": edges[i],
            "canonical_hi_hpf": edges[i + 1],
        }
        for i in range(len(edges) - 1)
    ]


def build_kimmel_bins() -> list[dict[str, object]]:
    return [
        {
            "stage_name": name,
            "stage_label": f"{name} ({lo:.2f}-{hi:.2f} hpf)",
            "canonical_lo_hpf": lo,
            "canonical_hi_hpf": hi,
        }
        for name, lo, hi in KIMMEL_PERIODS
    ]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--models", default="cnn_single,full")
    ap.add_argument("--scheme", choices=["kimmel_start", "fixed"], default="kimmel_start")
    ap.add_argument("--bins", default="")
    ap.add_argument("--out_csv", default="")
    args = ap.parse_args()

    outroot = Path(args.outroot)
    datasets = parse_csv_list(args.datasets)
    models = parse_csv_list(args.models)

    if args.scheme == "fixed":
        if not args.bins:
            raise ValueError("--bins is required when --scheme=fixed")
        bins = build_fixed_bins(parse_bins(args.bins))
    else:
        bins = build_kimmel_bins()

    rows: list[dict[str, object]] = []
    for ds in datasets:
        for model in models:
            points_csv = outroot / ds / model / "points.csv"
            if not points_csv.exists():
                raise FileNotFoundError(str(points_csv))

            grouped: list[list[tuple[float, float, float]]] = [[] for _ in bins]
            with points_csv.open("r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    x = float(row["x_true"])
                    err = float(row["err"])
                    abs_err = float(row["abs_err"])
                    for i, b in enumerate(bins):
                        lo = float(b["canonical_lo_hpf"])
                        hi = float(b["canonical_hi_hpf"])
                        if x >= lo and x < hi:
                            grouped[i].append((x, err, abs_err))
                            break

            for b, vals in zip(bins, grouped):
                if not vals:
                    continue
                xs = [x for x, _, _ in vals]
                errs = [e for _, e, _ in vals]
                abs_errs = [ae for _, _, ae in vals]
                n = len(vals)
                mae = sum(abs_errs) / n
                rmse = (sum(e * e for e in errs) / n) ** 0.5
                bias = sum(errs) / n
                rows.append(
                    {
                        "dataset": ds,
                        "model": model,
                        "scheme": args.scheme,
                        "stage_name": b["stage_name"],
                        "stage_label": b["stage_label"],
                        "canonical_lo_hpf": b["canonical_lo_hpf"],
                        "canonical_hi_hpf": b["canonical_hi_hpf"],
                        "observed_lo_hpf": min(xs),
                        "observed_hi_hpf": max(xs),
                        "n_points": n,
                        "mae": mae,
                        "rmse": rmse,
                        "bias": bias,
                    }
                )

    out_csv = Path(args.out_csv) if args.out_csv else (outroot / "stage_error" / "stage_error_by_bin.csv")
    fieldnames = [
        "dataset",
        "model",
        "scheme",
        "stage_name",
        "stage_label",
        "canonical_lo_hpf",
        "canonical_hi_hpf",
        "observed_lo_hpf",
        "observed_hi_hpf",
        "n_points",
        "mae",
        "rmse",
        "bias",
    ]
    write_csv(out_csv, rows, fieldnames)
    print("WROTE:", out_csv)


if __name__ == "__main__":
    main()
