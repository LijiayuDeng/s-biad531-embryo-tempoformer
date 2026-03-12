#!/usr/bin/env python3
"""
Direct stage-dependent tempo analysis from aggregated `points.csv`.

Outputs:
1. Kimmel-period piecewise linear slopes for each dataset/model.
2. Embryo-bootstrap confidence intervals for those stagewise slopes.
3. Local interval slopes from stage-averaged trajectories.
4. A compact SVG for ETF-full comparing local slopes between 28.5C and 25C.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import numpy as np


KIMMEL_PERIODS: list[tuple[str, float, float]] = [
    ("blastula", 2.25, 5.25),
    ("gastrula", 5.25, 10.33),
    ("segmentation", 10.33, 24.0),
    ("pharyngula", 24.0, 48.0),
]


def parse_csv_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def read_points_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "eid": row["eid"],
                    "x_true": float(row["x_true"]),
                    "y_pred": float(row["y_pred"]),
                    "err": float(row["err"]),
                }
            )
    return rows


def fit_ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    if len(x) < 2 or len(np.unique(x)) < 2:
        return float("nan"), float("nan"), float("nan")
    design = np.vstack([x, np.ones_like(x)]).T
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    corr = np.corrcoef(x, y)[0, 1]
    return float(slope), float(intercept), float(corr * corr)


def fit_ols_rows(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    x = np.asarray([float(r["x_true"]) for r in rows], dtype=np.float64)
    y = np.asarray([float(r["y_pred"]) for r in rows], dtype=np.float64)
    return fit_ols(x, y)


def bootstrap_stage_slope_ci(
    rows: list[dict[str, Any]], seed: int, n_boot: int
) -> tuple[float, float, int]:
    eids = sorted({str(r["eid"]) for r in rows})
    if len(eids) < 2:
        return float("nan"), float("nan"), 0
    by_eid: dict[str, list[dict[str, Any]]] = {eid: [] for eid in eids}
    for row in rows:
        by_eid[str(row["eid"])].append(row)
    rng = np.random.default_rng(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        sample_eids = rng.choice(eids, size=len(eids), replace=True)
        sample_rows: list[dict[str, Any]] = []
        for eid in sample_eids:
            sample_rows.extend(by_eid[eid])
        slope, _, _ = fit_ols_rows(sample_rows)
        if math.isfinite(slope):
            vals.append(slope)
    if not vals:
        return float("nan"), float("nan"), 0
    arr = np.asarray(vals, dtype=np.float64)
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975)), int(arr.size)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt(v: float, digits: int = 3) -> str:
    if np.isnan(v):
        return "nan"
    return f"{v:.{digits}f}"


def rows_to_markdown(rows: list[dict[str, str]], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row[h] for h in headers) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--out_dir", default="")
    ap.add_argument("--n_boot", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    outroot = Path(args.outroot)
    out_dir = Path(args.out_dir) if args.out_dir else outroot / "stage_tempo"
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets = parse_csv_list(args.datasets)
    models = parse_csv_list(args.models)

    piecewise_rows: list[dict[str, Any]] = []
    local_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []

    for model_idx, model in enumerate(models):
        stage_slope_map: dict[str, dict[str, float]] = {}
        stage_ci_map: dict[str, dict[str, tuple[float, float]]] = {}
        stage_boot_map: dict[str, dict[str, np.ndarray]] = {}
        for ds_idx, ds in enumerate(datasets):
            rows = read_points_csv(outroot / ds / model / "points.csv")
            stage_slope_map[ds] = {}
            stage_ci_map[ds] = {}
            stage_boot_map[ds] = {}

            for stage_idx, (stage_name, lo, hi) in enumerate(KIMMEL_PERIODS):
                sub = [r for r in rows if lo <= r["x_true"] < hi]
                slope, intercept, corr2 = fit_ols_rows(sub)
                stage_seed = args.seed + 10000 * model_idx + 1000 * ds_idx + 100 * stage_idx
                ci_lo, ci_hi, n_boot_eff = bootstrap_stage_slope_ci(
                    sub,
                    seed=stage_seed,
                    n_boot=args.n_boot,
                )
                # Recompute retained bootstrap values for delta-stage comparison.
                eids = sorted({str(r["eid"]) for r in sub})
                boot_vals: np.ndarray
                if len(eids) < 2:
                    boot_vals = np.asarray([], dtype=np.float64)
                else:
                    by_eid: dict[str, list[dict[str, Any]]] = {eid: [] for eid in eids}
                    for row in sub:
                        by_eid[str(row["eid"])].append(row)
                    rng = np.random.default_rng(stage_seed)
                    vals: list[float] = []
                    for _ in range(args.n_boot):
                        sample_eids = rng.choice(eids, size=len(eids), replace=True)
                        sample_rows: list[dict[str, Any]] = []
                        for eid in sample_eids:
                            sample_rows.extend(by_eid[eid])
                        m, _, _ = fit_ols_rows(sample_rows)
                        if math.isfinite(m):
                            vals.append(m)
                    boot_vals = np.asarray(vals, dtype=np.float64)
                stage_slope_map[ds][stage_name] = slope
                stage_ci_map[ds][stage_name] = (ci_lo, ci_hi)
                stage_boot_map[ds][stage_name] = boot_vals
                piecewise_rows.append(
                    {
                        "model": model,
                        "dataset": ds,
                        "stage_name": stage_name,
                        "canonical_lo_hpf": lo,
                        "canonical_hi_hpf": hi,
                        "n_points": len(sub),
                        "piecewise_slope": slope,
                        "piecewise_slope_ci_lo": ci_lo,
                        "piecewise_slope_ci_hi": ci_hi,
                        "n_boot_eff": n_boot_eff,
                        "piecewise_intercept": intercept,
                        "piecewise_corr2": corr2,
                    }
                )

            # Mean trajectory over each nominal start and local finite-difference slope.
            uniq_x = sorted({r["x_true"] for r in rows})
            mean_pairs: list[tuple[float, float]] = []
            for x_true in uniq_x:
                vals = [r["y_pred"] for r in rows if r["x_true"] == x_true]
                mean_pairs.append((x_true, float(np.mean(vals))))
            for (x0, y0), (x1, y1) in zip(mean_pairs[:-1], mean_pairs[1:]):
                local_rows.append(
                    {
                        "model": model,
                        "dataset": ds,
                        "x_lo_hpf": x0,
                        "x_hi_hpf": x1,
                        "x_mid_hpf": 0.5 * (x0 + x1),
                        "local_slope": (y1 - y0) / (x1 - x0),
                    }
                )

        # Add explicit delta rows after both datasets are seen.
        if "ID28C5_TEST" in stage_slope_map and "EXT25C_TEST" in stage_slope_map:
            delta_boot_map: dict[str, np.ndarray] = {}
            for stage_name, lo, hi in KIMMEL_PERIODS:
                m28 = stage_slope_map["ID28C5_TEST"].get(stage_name, float("nan"))
                m25 = stage_slope_map["EXT25C_TEST"].get(stage_name, float("nan"))
                v28 = stage_boot_map["ID28C5_TEST"].get(stage_name, np.asarray([], dtype=np.float64))
                v25 = stage_boot_map["EXT25C_TEST"].get(stage_name, np.asarray([], dtype=np.float64))
                if v28.size and v25.size:
                    n = min(v28.size, v25.size)
                    vd = v25[:n] - v28[:n]
                    delta_boot_map[stage_name] = vd
                    delta_ci_lo = float(np.quantile(vd, 0.025))
                    delta_ci_hi = float(np.quantile(vd, 0.975))
                    n_boot_eff = int(n)
                else:
                    delta_boot_map[stage_name] = np.asarray([], dtype=np.float64)
                    delta_ci_lo = float("nan")
                    delta_ci_hi = float("nan")
                    n_boot_eff = ""
                piecewise_rows.append(
                    {
                        "model": model,
                        "dataset": "delta_25C_minus_28C5",
                        "stage_name": stage_name,
                        "canonical_lo_hpf": lo,
                        "canonical_hi_hpf": hi,
                        "n_points": "",
                        "piecewise_slope": m25 - m28 if not (np.isnan(m25) or np.isnan(m28)) else float("nan"),
                        "piecewise_slope_ci_lo": delta_ci_lo,
                        "piecewise_slope_ci_hi": delta_ci_hi,
                        "n_boot_eff": n_boot_eff,
                        "piecewise_intercept": float("nan"),
                        "piecewise_corr2": float("nan"),
                    }
                )
            # Pairwise contrasts between stagewise slowdown estimates.
            stages = ["gastrula", "segmentation", "pharyngula"]
            for i, stage_a in enumerate(stages):
                for stage_b in stages[i + 1 :]:
                    va = delta_boot_map.get(stage_a, np.asarray([], dtype=np.float64))
                    vb = delta_boot_map.get(stage_b, np.asarray([], dtype=np.float64))
                    if va.size and vb.size:
                        n = min(va.size, vb.size)
                        diff = va[:n] - vb[:n]
                        contrast_rows.append(
                            {
                                "model": model,
                                "contrast": f"{stage_a}_minus_{stage_b}",
                                "estimate": float(np.mean(diff)),
                                "ci_lo": float(np.quantile(diff, 0.025)),
                                "ci_hi": float(np.quantile(diff, 0.975)),
                                "n_boot_eff": int(n),
                            }
                        )

    piecewise_csv = out_dir / "piecewise_stage_slopes.csv"
    local_csv = out_dir / "local_slope_by_interval.csv"
    contrast_csv = out_dir / "stage_delta_contrasts.csv"
    write_csv(
        piecewise_csv,
        piecewise_rows,
        [
            "model",
            "dataset",
            "stage_name",
            "canonical_lo_hpf",
            "canonical_hi_hpf",
            "n_points",
            "piecewise_slope",
            "piecewise_slope_ci_lo",
            "piecewise_slope_ci_hi",
            "n_boot_eff",
            "piecewise_intercept",
            "piecewise_corr2",
        ],
    )
    write_csv(
        local_csv,
        local_rows,
        ["model", "dataset", "x_lo_hpf", "x_hi_hpf", "x_mid_hpf", "local_slope"],
    )
    write_csv(
        contrast_csv,
        contrast_rows,
        ["model", "contrast", "estimate", "ci_lo", "ci_hi", "n_boot_eff"],
    )

    # Compact markdown table for the main full-model stage-dependent comparison.
    pretty_rows: list[dict[str, str]] = []
    stage_lookup = {
        (row["dataset"], row["stage_name"]): row
        for row in piecewise_rows
        if row["model"] == "full"
    }
    for stage_name, lo, hi in KIMMEL_PERIODS:
        r28 = stage_lookup[("ID28C5_TEST", stage_name)]
        r25 = stage_lookup[("EXT25C_TEST", stage_name)]
        rd = stage_lookup[("delta_25C_minus_28C5", stage_name)]
        pretty_rows.append(
            {
                "Kimmel period": stage_name.capitalize(),
                "Canonical window (hpf)": f"{lo:.2f}-{hi:.2f}",
                "28.5C piecewise slope [95% CI]": (
                    f"{fmt(float(r28['piecewise_slope']))} "
                    f"[{fmt(float(r28['piecewise_slope_ci_lo']))}, {fmt(float(r28['piecewise_slope_ci_hi']))}]"
                ),
                "25C piecewise slope [95% CI]": (
                    f"{fmt(float(r25['piecewise_slope']))} "
                    f"[{fmt(float(r25['piecewise_slope_ci_lo']))}, {fmt(float(r25['piecewise_slope_ci_hi']))}]"
                ),
                "delta slope (25C-28.5C) [95% CI]": (
                    f"{fmt(float(rd['piecewise_slope']))} "
                    f"[{fmt(float(rd['piecewise_slope_ci_lo']))}, {fmt(float(rd['piecewise_slope_ci_hi']))}]"
                ),
            }
        )
    md_path = out_dir / "stage_tempo_full_summary.md"
    headers = [
        "Kimmel period",
        "Canonical window (hpf)",
        "28.5C piecewise slope [95% CI]",
        "25C piecewise slope [95% CI]",
        "delta slope (25C-28.5C) [95% CI]",
    ]
    md_path.write_text(rows_to_markdown(pretty_rows, headers), encoding="utf-8")

    # ETF-full local-slope figure.
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    for ds, color, label in [
        ("ID28C5_TEST", "#1f4e79", "28.5C"),
        ("EXT25C_TEST", "#b24a2a", "25C"),
    ]:
        xs = [float(r["x_mid_hpf"]) for r in local_rows if r["model"] == "full" and r["dataset"] == ds]
        ys = [float(r["local_slope"]) for r in local_rows if r["model"] == "full" and r["dataset"] == ds]
        ax.plot(xs, ys, marker="o", markersize=3, linewidth=1.8, color=color, label=label)
    ax.axhline(1.0, color="#666666", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Nominal interval midpoint (hpf)")
    ax.set_ylabel("Local slope d(y_pred)/d(x_true)")
    ax.set_title("ETF-full local tempo slope by developmental window")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.25, linewidth=0.6)
    fig.tight_layout()
    fig_path = out_dir / "full_local_slope_by_interval.svg"
    fig.savefig(fig_path)
    plt.close(fig)

    print(f"WROTE: {piecewise_csv}")
    print(f"WROTE: {local_csv}")
    print(f"WROTE: {contrast_csv}")
    print(f"WROTE: {md_path}")
    print(f"WROTE: {fig_path}")


if __name__ == "__main__":
    main()
