#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmbryoTempoFormer — Continuous effect-size power curve
======================================================

Why this script exists
----------------------
`analysis/power_curve.py` answers one question:
  "Given a fixed effect (the observed 25C vs 28.5C shift), how does power change with E?"

This script answers a complementary question:
  "Across a CONTINUOUS range of effect magnitudes (default |delta m| from 0 to 0.10),
   what embryo budget E is required to reach a target power (E80/E90/E95)?"

Core idea
---------
For each model:
1. Read embryo-level `m_anchor` for condition A (default: EXT25C_TEST) and
   condition B (default: ID28C5_TEST).
2. Build a pooled centered residual distribution:
      res = concat(A - mean(A), B - mean(B))
3. For each target effect magnitude `delta_abs`:
   - set signed shift `delta_signed = -delta_abs` (slower A than B)
   - define synthetic mean for A:
        mean_A = mean_B + delta_signed
   - sample synthetic embryos from `mean_A + res` and `mean_B + res`
   - run embryo-bootstrap CI decision (CI excludes 0 => "detected")
4. Repeat over embryo budgets E and summarize:
   - full power table: power(E, delta_abs, model)
   - threshold table: E80/E90/E95 as functions of delta_abs
5. Apply shape-constrained postprocessing (enabled by default):
   - power(E) is forced non-decreasing for fixed delta_abs
   - E-threshold(delta_abs) is forced non-increasing for larger |delta m|

Outputs
-------
1) CSV: continuous_power_by_model.csv
   row-level power surface across model x delta_abs x E
2) CSV: continuous_thresholds_by_model.csv
   threshold curves (E80/E90/E95) across model x delta_abs
3) SVG: continuous_E80_by_model.svg
   E80 vs |delta m| for all models
4) SVG: continuous_full_E80_E90_E95.svg
   E80/E90/E95 vs |delta m| for the full model

Notes
-----
- Inference unit remains embryo-level (never window-level).
- This is planning-oriented simulation, not a guarantee for future datasets.
- SVG plotting is dependency-free (works even without matplotlib).
- Shape-constrained postprocessing reduces Monte-Carlo jitter while preserving
  conservative threshold logic.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray


# Numeric array alias used throughout this script to satisfy strict type checkers.
FloatArray = NDArray[np.float64]


# -----------------------------
# I/O helpers
# -----------------------------


def read_col(csv_path: Path, col: str) -> FloatArray:
    """Read one numeric column from a CSV into a float64 numpy array."""
    vals: List[float] = []
    with csv_path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or col not in r.fieldnames:
            raise ValueError(f"Column '{col}' not found in {csv_path}; fields={r.fieldnames}")
        for row in r:
            try:
                v = float(row[col])
            except Exception:
                continue
            if math.isfinite(v):
                vals.append(v)
    if not vals:
        raise ValueError(f"No finite values for column '{col}' in {csv_path}")
    return np.asarray(vals, dtype=np.float64)


def parse_csv_list(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def parse_int_list(s: str) -> List[int]:
    out = sorted(set(int(x.strip()) for x in s.split(",") if x.strip()))
    if not out:
        raise ValueError("Parsed empty integer list")
    return out


def build_delta_grid(delta_max: float, delta_step: float) -> List[float]:
    """
    Build [0, step, 2*step, ..., delta_max] with stable rounding.
    """
    n = int(round(delta_max / delta_step))
    return [round(i * delta_step, 10) for i in range(n + 1)]


def build_axis_ticks(y_min: float, y_max: float, step: float) -> List[float]:
    """Build evenly spaced y-axis ticks."""
    if step <= 0:
        raise ValueError("y_tick_step must be > 0")
    start = math.ceil(y_min / step) * step
    out: List[float] = []
    v = start
    while v <= y_max + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


# -----------------------------
# Statistical core
# -----------------------------


def bootstrap_ci_delta(m_a: FloatArray, m_b: FloatArray, b_boot: int, rng: np.random.Generator) -> Tuple[float, float]:
    """
    95% percentile bootstrap CI for:
      delta = mean(m_a) - mean(m_b)
    where bootstrap resampling happens within each sampled embryo set.
    """
    n_a, n_b = m_a.size, m_b.size
    ia: NDArray[np.int64] = np.asarray(rng.integers(0, n_a, size=(b_boot, n_a)), dtype=np.int64)
    ib: NDArray[np.int64] = np.asarray(rng.integers(0, n_b, size=(b_boot, n_b)), dtype=np.int64)
    d: FloatArray = np.asarray(m_a[ia].mean(axis=1) - m_b[ib].mean(axis=1), dtype=np.float64)
    lo = float(np.quantile(d, 0.025))
    hi = float(np.quantile(d, 0.975))
    return lo, hi


def simulate_model_continuous(
    *,
    m_a_obs: FloatArray,
    m_b_obs: FloatArray,
    e_list: Sequence[int],
    delta_abs_grid: Sequence[float],
    r_outer: int,
    b_boot: int,
    rng: np.random.Generator,
) -> List[Dict[str, Any]]:
    """
    Simulate power surface for one model over (delta_abs, E).

    We use pooled centered residuals:
      res = concat(m_a_obs - mean(m_a_obs), m_b_obs - mean(m_b_obs))
    and set synthetic means by target shift.
    """
    mean_b = float(np.mean(m_b_obs))
    res: FloatArray = np.asarray(
        np.concatenate([m_a_obs - np.mean(m_a_obs), m_b_obs - np.mean(m_b_obs)]),
        dtype=np.float64,
    )

    rows: List[Dict[str, Any]] = []
    for delta_abs in delta_abs_grid:
        # Convention: negative shift means slower condition A.
        delta_signed = -float(delta_abs)
        mean_a = mean_b + delta_signed

        for e in e_list:
            success = 0
            for _ in range(r_outer):
                # Synthetic embryo-level draws for this virtual experiment.
                idx_a: NDArray[np.int64] = np.asarray(rng.integers(0, res.size, size=e), dtype=np.int64)
                idx_b: NDArray[np.int64] = np.asarray(rng.integers(0, res.size, size=e), dtype=np.int64)
                m_a: FloatArray = np.asarray(mean_a + res[idx_a], dtype=np.float64)
                m_b: FloatArray = np.asarray(mean_b + res[idx_b], dtype=np.float64)

                lo, hi = bootstrap_ci_delta(m_a, m_b, b_boot=b_boot, rng=rng)
                detected = (lo > 0.0) or (hi < 0.0)  # CI excludes 0
                success += int(detected)

            power = success / float(r_outer)
            rows.append(
                {
                    "delta_abs": float(delta_abs),
                    "delta_signed": float(delta_signed),
                    "E_per_group": int(e),
                    "power": float(power),
                }
            )
    return rows


def thresholds_from_surface(
    *,
    rows: Sequence[Dict[str, Any]],
    e_list: Sequence[int],
    targets: Sequence[float],
) -> List[Dict[str, Any]]:
    """
    Convert row-level power surface -> threshold curves E80/E90/E95.
    """
    # Group by delta_abs.
    by_delta: Dict[float, List[Dict[str, Any]]] = {}
    for r in rows:
        d = float(r["delta_abs"])
        by_delta.setdefault(d, []).append(r)

    out: List[Dict[str, Any]] = []
    for d in sorted(by_delta.keys()):
        rr = sorted(by_delta[d], key=lambda x: int(x["E_per_group"]))
        row: Dict[str, Any] = {
            "delta_abs": d,
            "delta_signed": -d,
        }
        for t in targets:
            thr: Optional[int] = None
            for r in rr:
                if float(r["power"]) >= t:
                    thr = int(r["E_per_group"])
                    break
            key = f"E{int(round(t * 100))}"
            row[key] = thr if thr is not None else f">{max(e_list)}"
        out.append(row)
    return out


def enforce_monotone_power_over_e(
    *,
    rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Enforce monotonicity: power should be non-decreasing as E increases.

    This is a shape-constrained postprocessing step to reduce finite-simulation
    jitter near threshold boundaries.
    """
    by_delta: Dict[float, List[Dict[str, Any]]] = {}
    for r in rows:
        d = float(r["delta_abs"])
        by_delta.setdefault(d, []).append(dict(r))

    out: List[Dict[str, Any]] = []
    for d in sorted(by_delta.keys()):
        rr = sorted(by_delta[d], key=lambda x: int(x["E_per_group"]))
        best = -1.0
        for r in rr:
            p = float(r["power"])
            best = max(best, p)
            r["power_raw"] = p
            r["power"] = best
            out.append(r)
    return out


def enforce_monotone_thresholds_vs_delta(
    *,
    rows: Sequence[Dict[str, Any]],
    targets: Sequence[float],
    e_max: int,
) -> List[Dict[str, Any]]:
    """
    Enforce monotonicity: required E should be non-increasing as |delta m| grows.
    """
    rr = sorted((dict(r) for r in rows), key=lambda x: float(x["delta_abs"]))
    for t in targets:
        key = f"E{int(round(t * 100))}"
        best = e_max + 1
        for r in rr:
            v = r[key]
            cur = e_max + 1 if str(v).startswith(">") else int(v)
            best = min(best, cur)
            r[key] = f">{e_max}" if best > e_max else best
    return rr


# -----------------------------
# Lightweight SVG plotting
# -----------------------------


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _to_float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s.startswith(">"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def _smooth_segment_monotone(
    seg: Sequence[Tuple[float, float]], samples_per_interval: int = 14
) -> List[Tuple[float, float]]:
    """
    Smooth one (x, y) segment using monotone cubic Hermite interpolation.

    Why monotone spline instead of generic cubic spline:
    - Avoids visually misleading overshoot/wiggles.
    - Preserves the trend direction in threshold curves (typically non-increasing
      with larger |delta m|).
    - Keeps endpoints exact while providing a cleaner curve than straight lines.

    This implementation follows the Fritsch-Carlson slope-limiting rule.
    """
    if len(seg) < 3:
        return list(seg)

    x: FloatArray = np.asarray([p[0] for p in seg], dtype=np.float64)
    y: FloatArray = np.asarray([p[1] for p in seg], dtype=np.float64)
    h: FloatArray = np.diff(x)
    if np.any(h <= 0):
        # Fallback to original points if x is not strictly increasing.
        return list(seg)

    d: FloatArray = np.asarray(np.diff(y) / h, dtype=np.float64)
    n = len(x)
    m: FloatArray = np.zeros(n, dtype=np.float64)
    m[0] = d[0]
    m[-1] = d[-1]
    for i in range(1, n - 1):
        m[i] = 0.5 * (d[i - 1] + d[i])

    # Slope limiting to enforce monotonicity.
    for i in range(n - 1):
        if d[i] == 0.0:
            m[i] = 0.0
            m[i + 1] = 0.0
            continue
        a = m[i] / d[i]
        b = m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9.0:
            t = 3.0 / math.sqrt(s)
            m[i] = t * a * d[i]
            m[i + 1] = t * b * d[i]

    out: List[Tuple[float, float]] = [(float(x[0]), float(y[0]))]
    for i in range(n - 1):
        xi, xi1 = x[i], x[i + 1]
        yi, yi1 = y[i], y[i + 1]
        hi = xi1 - xi
        mi, mi1 = m[i], m[i + 1]

        for k in range(1, samples_per_interval + 1):
            t = float(k) / float(samples_per_interval)
            # Cubic Hermite basis
            h00 = 2.0 * t * t * t - 3.0 * t * t + 1.0
            h10 = t * t * t - 2.0 * t * t + t
            h01 = -2.0 * t * t * t + 3.0 * t * t
            h11 = t * t * t - t * t

            xs = xi + t * hi
            ys = h00 * yi + h10 * hi * mi + h01 * yi1 + h11 * hi * mi1
            out.append((float(xs), float(ys)))

    return out


def write_svg_line_chart(
    *,
    out_svg: Path,
    title: str,
    x_label: str,
    y_label: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    series: Sequence[Dict[str, Any]],
    y_ticks: Sequence[float],
    footnote: str = "",
) -> None:
    """
    Render a simple multi-line chart as SVG without third-party dependencies.

    `series` item format:
      {
        "name": str,
        "color": "#RRGGBB",
        "points": List[Tuple[x, y_or_none]]
      }
    """
    width, height = 1000, 620
    ml, mr, mt, mb = 90, 260, 70, 90
    plot_w = width - ml - mr
    plot_h = height - mt - mb

    def sx(x: float) -> float:
        if x_max == x_min:
            return ml
        return ml + (x - x_min) / (x_max - x_min) * plot_w

    def sy(y: float) -> float:
        if y_max == y_min:
            return mt + plot_h
        return mt + (1.0 - (y - y_min) / (y_max - y_min)) * plot_h

    palette = [s["color"] for s in series]
    _ = palette  # keeps lint quiet if unused

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')

    # Title
    lines.append(
        f'<text x="{ml}" y="36" font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="bold">{_svg_escape(title)}</text>'
    )

    # Axes
    lines.append(f'<line x1="{ml}" y1="{mt + plot_h}" x2="{ml + plot_w}" y2="{mt + plot_h}" stroke="#111" stroke-width="1.5"/>')
    lines.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}" stroke="#111" stroke-width="1.5"/>')

    # X ticks at every 0.05
    xt = np.arange(x_min, x_max + 1e-9, 0.05)
    for x in xt:
        xx = sx(float(x))
        lines.append(f'<line x1="{xx:.2f}" y1="{mt + plot_h}" x2="{xx:.2f}" y2="{mt + plot_h + 6}" stroke="#111" stroke-width="1"/>')
        lines.append(
            f'<text x="{xx:.2f}" y="{mt + plot_h + 24}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="12">{x:.2f}</text>'
        )
        lines.append(
            f'<line x1="{xx:.2f}" y1="{mt}" x2="{xx:.2f}" y2="{mt + plot_h}" stroke="#eee" stroke-width="1"/>'
        )

    # Y ticks
    for y in y_ticks:
        yy = sy(float(y))
        lines.append(f'<line x1="{ml - 6}" y1="{yy:.2f}" x2="{ml}" y2="{yy:.2f}" stroke="#111" stroke-width="1"/>')
        lines.append(
            f'<text x="{ml - 10}" y="{yy + 4:.2f}" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="12">{int(y) if float(y).is_integer() else y}</text>'
        )
        lines.append(
            f'<line x1="{ml}" y1="{yy:.2f}" x2="{ml + plot_w}" y2="{yy:.2f}" stroke="#f2f2f2" stroke-width="1"/>'
        )

    # Axis labels
    lines.append(
        f'<text x="{ml + plot_w / 2:.2f}" y="{height - 30}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="14">{_svg_escape(x_label)}</text>'
    )
    lines.append(
        f'<text transform="translate(24 {mt + plot_h / 2:.2f}) rotate(-90)" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="14">{_svg_escape(y_label)}</text>'
    )

    # Curves
    for s in series:
        name = str(s["name"])
        color = str(s["color"])
        pts = s["points"]

        # Split into contiguous segments (skip None gaps)
        seg: List[Tuple[float, float]] = []
        segments: List[List[Tuple[float, float]]] = []
        for x, y in pts:
            if y is None:
                if seg:
                    segments.append(seg)
                    seg = []
                continue
            seg.append((x, y))
        if seg:
            segments.append(seg)

        for g in segments:
            # Render as monotone-smoothed curve (densified polyline).
            gg = _smooth_segment_monotone(g, samples_per_interval=14)
            p = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in gg)
            lines.append(
                f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="2.5"/>'
            )

        # Draw markers for observed points
        for x, y in pts:
            if y is None:
                continue
            lines.append(
                f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="2.6" fill="{color}" />'
            )

        _ = name

    # Legend
    lx = ml + plot_w + 24
    ly = mt + 20
    lines.append(
        f'<text x="{lx}" y="{ly - 10}" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="bold">Legend</text>'
    )
    for i, s in enumerate(series):
        yy = ly + i * 24
        color = str(s["color"])
        name = _svg_escape(str(s["name"]))
        lines.append(f'<line x1="{lx}" y1="{yy}" x2="{lx + 26}" y2="{yy}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{lx + 34}" y="{yy + 4}" font-family="Arial, Helvetica, sans-serif" font-size="12">{name}</text>')

    # Footnote
    if footnote:
        lines.append(
            f'<text x="{ml}" y="{height - 8}" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#555">{_svg_escape(footnote)}</text>'
        )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines), encoding="utf-8")


# -----------------------------
# Main
# -----------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Continuous effect-size power curve (embryo-level)")
    ap.add_argument("--outroot", required=True, help="Evaluation root, e.g. runs/paper_eval_YYYYMMDD_HHMMSS")
    ap.add_argument("--out_dir", default="", help="Output directory (default: <outroot>/continuous_power)")
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--a_test", default="EXT25C_TEST", help="Condition A split folder (default 25C)")
    ap.add_argument("--b_test", default="ID28C5_TEST", help="Condition B split folder (default 28.5C)")
    ap.add_argument("--m_col", default="m_anchor")
    ap.add_argument("--E_list", default="2,3,4,6,8,10,12,14,16,18,20,22")
    ap.add_argument("--delta_max", type=float, default=0.10)
    ap.add_argument("--delta_step", type=float, default=0.002)
    ap.add_argument("--R", type=int, default=1200, help="Outer repeats")
    ap.add_argument("--B_boot", type=int, default=800, help="Inner bootstrap repeats")
    ap.add_argument("--seed", type=int, default=20260310)
    ap.add_argument("--y_min_plot", type=float, default=0.0, help="Y-axis lower bound for SVG plots")
    ap.add_argument("--y_max_plot", type=float, default=23.0, help="Y-axis upper bound for SVG plots")
    ap.add_argument("--y_tick_step", type=float, default=1.0, help="Y-axis tick interval for SVG plots")
    ap.add_argument("--enforce_monotone_power_e", type=int, default=1, choices=[0, 1], help="Apply cumulative-max power(E) smoothing")
    ap.add_argument("--enforce_monotone_threshold_delta", type=int, default=1, choices=[0, 1], help="Apply cumulative-min threshold(delta) smoothing")
    args = ap.parse_args()

    outroot = Path(args.outroot)
    if not outroot.exists():
        raise FileNotFoundError(f"outroot not found: {outroot}")

    out_dir = Path(args.out_dir) if args.out_dir else (outroot / "continuous_power")
    out_dir.mkdir(parents=True, exist_ok=True)

    models = parse_csv_list(args.models)
    e_list = parse_int_list(args.E_list)
    delta_abs_grid = build_delta_grid(args.delta_max, args.delta_step)
    targets = [0.80, 0.90, 0.95]
    y_ticks = build_axis_ticks(args.y_min_plot, args.y_max_plot, args.y_tick_step)

    rng = np.random.default_rng(args.seed)

    power_rows_all: List[Dict[str, Any]] = []
    thr_rows_all: List[Dict[str, Any]] = []

    for model in models:
        csv_a = outroot / args.a_test / model / "embryo.csv"
        csv_b = outroot / args.b_test / model / "embryo.csv"
        if not csv_a.exists() or not csv_b.exists():
            raise FileNotFoundError(f"Missing embryo.csv for model={model}: {csv_a} | {csv_b}")

        a_obs = read_col(csv_a, args.m_col)
        b_obs = read_col(csv_b, args.m_col)
        print(f"[{model}] nA={a_obs.size} nB={b_obs.size} ...")

        rows_model = simulate_model_continuous(
            m_a_obs=a_obs,
            m_b_obs=b_obs,
            e_list=e_list,
            delta_abs_grid=delta_abs_grid,
            r_outer=args.R,
            b_boot=args.B_boot,
            rng=rng,
        )
        if args.enforce_monotone_power_e == 1:
            rows_model = enforce_monotone_power_over_e(rows=rows_model)

        for r in rows_model:
            r["model"] = model
            r["R"] = args.R
            r["B_boot"] = args.B_boot
            r["seed"] = args.seed
            r["monotone_power_e"] = args.enforce_monotone_power_e
            r["monotone_threshold_delta"] = args.enforce_monotone_threshold_delta
            r["method"] = (
                "pooled_residual_shift+bootstrap_CI_excludes_zero"
                f"+monotone_powerE={args.enforce_monotone_power_e}"
            )
            if "power_raw" not in r:
                # Keep CSV schema stable even when monotone smoothing is disabled.
                r["power_raw"] = r["power"]
            power_rows_all.append(r)

        thr_model = thresholds_from_surface(rows=rows_model, e_list=e_list, targets=targets)
        if args.enforce_monotone_threshold_delta == 1:
            thr_model = enforce_monotone_thresholds_vs_delta(
                rows=thr_model,
                targets=targets,
                e_max=max(e_list),
            )
        for r in thr_model:
            r["model"] = model
            r["monotone_power_e"] = args.enforce_monotone_power_e
            r["monotone_threshold_delta"] = args.enforce_monotone_threshold_delta
            thr_rows_all.append(r)

    # Write CSV outputs
    power_csv = out_dir / "continuous_power_by_model.csv"
    with power_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "delta_abs",
                "delta_signed",
                "E_per_group",
                "power",
                "power_raw",
                "R",
                "B_boot",
                "seed",
                "monotone_power_e",
                "monotone_threshold_delta",
                "method",
            ],
        )
        w.writeheader()
        w.writerows(power_rows_all)
    print("WROTE:", power_csv)

    thr_csv = out_dir / "continuous_thresholds_by_model.csv"
    with thr_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "delta_abs",
                "delta_signed",
                "E80",
                "E90",
                "E95",
                "monotone_power_e",
                "monotone_threshold_delta",
            ],
        )
        w.writeheader()
        w.writerows(thr_rows_all)
    print("WROTE:", thr_csv)

    # Build lookup for plotting
    by_model: Dict[str, Dict[float, Dict[str, Any]]] = {}
    for r in thr_rows_all:
        m = str(r["model"])
        d = float(r["delta_abs"])
        by_model.setdefault(m, {})[d] = r

    # Plot 1: E80 by model
    colors = {
        "cnn_single": "#009E73",
        "meanpool": "#0072B2",
        "nocons": "#E69F00",
        "full": "#D55E00",
    }
    e80_series: List[Dict[str, Any]] = []
    for m in models:
        pts: List[Tuple[float, Optional[float]]] = []
        for d in delta_abs_grid:
            rr = by_model[m][d]
            y = _to_float_or_none(rr["E80"])
            pts.append((float(d), y))
        e80_series.append({"name": m, "color": colors.get(m, "#333333"), "points": pts})

    svg1 = out_dir / "continuous_E80_by_model.svg"
    write_svg_line_chart(
        out_svg=svg1,
        title="Continuous Effect-Size Planning Curve (E80)",
        x_label="|delta m|",
        y_label="Required embryos per group (E80)",
        x_min=0.0,
        x_max=args.delta_max,
        y_min=args.y_min_plot,
        y_max=args.y_max_plot,
        y_ticks=y_ticks,
        series=e80_series,
        footnote=(
            f"Embryo-level simulation; R={args.R}, B_boot={args.B_boot}; "
            f"monotone_powerE={args.enforce_monotone_power_e}, "
            f"monotone_thresholdDelta={args.enforce_monotone_threshold_delta}; "
            "'>22' shown as gaps"
        ),
    )
    print("WROTE:", svg1)

    # Plot 2: full model E80/E90/E95
    if "full" in by_model:
        full_series: List[Dict[str, Any]] = []
        for key, color in [("E80", "#D55E00"), ("E90", "#0072B2"), ("E95", "#009E73")]:
            pts: List[Tuple[float, Optional[float]]] = []
            for d in delta_abs_grid:
                rr = by_model["full"][d]
                y = _to_float_or_none(rr[key])
                pts.append((float(d), y))
            full_series.append({"name": key, "color": color, "points": pts})

        svg2 = out_dir / "continuous_full_E80_E90_E95.svg"
        write_svg_line_chart(
            out_svg=svg2,
            title="Continuous Effect-Size Planning Curve (full model)",
            x_label="|delta m|",
            y_label="Required embryos per group",
            x_min=0.0,
            x_max=args.delta_max,
            y_min=args.y_min_plot,
            y_max=args.y_max_plot,
            y_ticks=y_ticks,
            series=full_series,
            footnote=(
                f"Embryo-level simulation; R={args.R}, B_boot={args.B_boot}; "
                f"monotone_powerE={args.enforce_monotone_power_e}, "
                f"monotone_thresholdDelta={args.enforce_monotone_threshold_delta}; "
                "'>22' shown as gaps"
            ),
        )
        print("WROTE:", svg2)


if __name__ == "__main__":
    main()
