#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EmbryoTempoFormer — publication-grade, squarer figures (top-tier style)

Inputs under OUTROOT:
  ID28C5_TEST/<model>/summary.json
  EXT25C_TEST/<model>/embryo.csv
  CI_<model>_m_anchor.json

Outputs under OUTROOT/figures_jobs (PNG + PDF):
  Fig2_ID_ablation.(png/pdf)
  Fig3_EXT_m_anchor.(png/pdf)
  Fig3_EXT_rmse_resid.(png/pdf)
  Fig3_delta_m_forest.(png/pdf)

No pandas required. Requires numpy + matplotlib.
"""

from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any, cast

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
from numpy.typing import NDArray


MODELS = ["cnn_single", "meanpool", "nocons", "full"]
LABELS = ["CNN single", "Meanpool", "No-cons", "Full"]

# More restrained palette: highlight key comparisons, de-emphasize others
COLORS = {
    "cnn_single": "#9AA0A6",  # gray
    "meanpool":   "#C0C6CF",  # lighter gray-blue
    "nocons":     "#E69F00",  # orange (ablation)
    "full":       "#D33F49",  # red (final)
}

JSONDict = dict[str, Any]
FloatArray = NDArray[np.float64]


def ensure(p: Path) -> None:
    if not p.exists():
        raise FileNotFoundError(str(p))

def read_json(p: Path) -> JSONDict:
    with open(p, "r", encoding="utf-8") as f:
        return cast(JSONDict, json.load(f))

def read_csv_col(p: Path, col: str) -> FloatArray:
    vals: list[float] = []
    with open(p, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if col not in (r.fieldnames or []):
            raise ValueError(f"Missing column '{col}' in {p}. Have {r.fieldnames}")
        for row in r:
            try:
                v = float(row[col])
            except Exception:
                continue
            if np.isfinite(v):
                vals.append(v)
    if not vals:
        raise ValueError(f"No numeric values for '{col}' in {p}")
    return np.array(vals, dtype=np.float64)

def set_style() -> None:
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,

        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,

        "axes.facecolor": "white",
        "axes.edgecolor": "#111111",
        "axes.linewidth": 1.2,
        "axes.spines.top": False,
        "axes.spines.right": False,

        "xtick.major.size": 4,
        "ytick.major.size": 4,
        "xtick.major.width": 1.0,
        "ytick.major.width": 1.0,

        "lines.linewidth": 2.0,
        "axes.grid": False,
        "grid.color": "#DADCE0",
        "grid.linewidth": 0.8,
        "grid.alpha": 0.6,
    })

def save_both(fig: Figure, out_base: Path, dpi: int) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_base.with_suffix(".png")), dpi=dpi)
    fig.savefig(str(out_base.with_suffix(".pdf")))
    print("WROTE:", out_base.with_suffix(".png"))
    print("WROTE:", out_base.with_suffix(".pdf"))

def _nice_xlim_from_ci(lo: FloatArray, hi: FloatArray, pad: float = 0.15) -> tuple[float, float]:
    mn = float(np.min(lo))
    mx = float(np.max(hi))
    span = mx - mn
    if span <= 1e-12:
        span = 1.0
    return (mn - pad*span, mx + pad*span)

def _jitter(n: int, scale: float, seed: int = 0) -> FloatArray:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=0.0, scale=scale, size=n).astype(np.float64)

def violin_quartile_jitter(
    ax: Axes,
    data_list: list[FloatArray],
    x: FloatArray,
    colors: list[str],
    ylabel: str,
    title: str,
    jitter: bool = True,
) -> None:
    """
    Violin + IQR bar + median dot + optional light jitter points.
    (raincloud-lite without seaborn)
    """
    parts = cast(dict[str, Any], ax.violinplot(
        data_list,
        positions=x,
        widths=0.78,
        showmeans=False,
        showextrema=False,
        showmedians=False,
    ))
    bodies = cast(list[Any], parts["bodies"])
    for body, c in zip(bodies, colors):
        body.set_facecolor(c)
        body.set_edgecolor(c)
        body.set_alpha(0.18)
        body.set_linewidth(1.2)

    # IQR + median, plus optional jitter points
    for xi, d, c in zip(x, data_list, colors):
        q = np.quantile(d, np.array([0.25, 0.5, 0.75], dtype=np.float64))
        q1 = float(q[0])
        med = float(q[1])
        q3 = float(q[2])
        ax.plot([xi, xi], [q1, q3], color=c, linewidth=3.0, solid_capstyle="round", zorder=3)
        ax.scatter([xi], [med], s=34, color=c, edgecolor="white", linewidth=0.9, zorder=4)

        if jitter:
            # light points (do not dominate)
            j = _jitter(len(d), scale=0.06, seed=42)
            ax.scatter(
                np.full(d.shape, float(xi), dtype=np.float64) + j,
                d,
                s=8,
                color=c,
                alpha=0.10,
                linewidths=0,
                zorder=2,
            )

    ax.yaxis.grid(True, alpha=0.22)
    ax.set_xticks(x, LABELS)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

def fig2_id_ablation(outroot: Path, outdir: Path, dpi: int) -> None:
    """
    Fig2: make it squarer by stacking panels vertically (2x1).

    Panel A: MAE (filled) vs RMSE (hollow), color = model
    Panel B: residual RMSE lollipop (anchored fit), sorted best->worst
    """
    import matplotlib.pyplot as plt

    mae: list[float] = []
    rmse: list[float] = []
    resid: list[float] = []
    n_emb: int | None = None
    n_pts: int | None = None
    for m in MODELS:
        p = outroot / "ID28C5_TEST" / m / "summary.json"
        ensure(p)
        d = read_json(p)
        mae.append(float(d["global_metrics_points"]["mae"]))
        rmse.append(float(d["global_metrics_points"]["rmse"]))
        resid.append(float(d["fit_anchor_T0"]["rmse_resid"]))
        n_emb = int(d["global_metrics_points"]["n_embryos"])
        n_pts = int(d["global_metrics_points"]["n_points"])

    x: FloatArray = np.arange(len(MODELS), dtype=np.float64)
    colors = [COLORS[m] for m in MODELS]

    fig: Figure = cast(Figure, plt.figure(figsize=(6.8, 6.8)))  # squarer
    gs = fig.add_gridspec(2, 1, height_ratios=[1.05, 1.0], hspace=0.35)

    # Panel A
    ax: Axes = cast(Axes, fig.add_subplot(gs[0, 0]))
    dx = 0.13
    for i, m in enumerate(MODELS):
        c = COLORS[m]
        ax.plot([x[i]-dx, x[i]+dx], [mae[i], rmse[i]], color=c, alpha=0.25, zorder=1)
        ax.scatter(x[i]-dx, mae[i], s=70, color=c, edgecolor="white", linewidth=0.9, zorder=3)  # MAE filled
        ax.scatter(x[i]+dx, rmse[i], s=70, facecolor="white", edgecolor=c, linewidth=2.0, zorder=3)  # RMSE hollow

    ax.yaxis.grid(True, alpha=0.22)
    ax.set_xticks(x, LABELS)
    ax.set_ylabel("Error (hours)")
    ax.set_title(f"ID 28.5°C test (n={n_emb} embryos, {n_pts} points; stride=8)")

    mae_h = Line2D([0], [0], marker="o", linestyle="none",
                   markerfacecolor="#111111", markeredgecolor="#111111",
                   markersize=7, label="MAE (filled)")
    rmse_h = Line2D([0], [0], marker="o", linestyle="none",
                    markerfacecolor="white", markeredgecolor="#111111",
                    markersize=7, label="RMSE (hollow)")
    ax.legend(handles=[mae_h, rmse_h], frameon=False, loc="upper left")

    # Panel B (sorted by residual)
    ax2: Axes = cast(Axes, fig.add_subplot(gs[1, 0]))
    order: list[int] = [int(i) for i in np.argsort(np.array(resid, dtype=np.float64))]
    y: FloatArray = np.arange(len(order), dtype=np.float64)
    y_labels = [LABELS[i] for i in order]
    for yy, idx in zip(y, order):
        m = MODELS[idx]
        c = COLORS[m]
        r = resid[idx]
        ax2.plot([0, r], [yy, yy], color=c, alpha=0.65, linewidth=3.0, solid_capstyle="round")
        ax2.scatter([r], [yy], s=72, color=c, edgecolor="white", linewidth=0.9, zorder=3)

    ax2.xaxis.grid(True, alpha=0.22)
    ax2.set_yticks(y, y_labels)
    ax2.set_xlabel("Residual RMSE (hours)")
    ax2.set_title("Anchored-fit scatter (y−4.5 = m(x−4.5))")

    fig.suptitle("Figure 2. In-distribution ablation on 28.5°C test", y=1.02, fontsize=13)
    save_both(fig, outdir / "Fig2_ID_ablation", dpi=dpi)
    plt.close(fig)

def fig3_ext_m_anchor(outroot: Path, outdir: Path, dpi: int) -> None:
    import matplotlib.pyplot as plt
    m_list: list[FloatArray] = []
    n_emb: int | None = None
    for m in MODELS:
        p = outroot / "EXT25C_TEST" / m / "embryo.csv"
        ensure(p)
        arr = read_csv_col(p, "m_anchor")
        m_list.append(arr)
        n_emb = int(arr.size)

    colors = [COLORS[m] for m in MODELS]
    x: FloatArray = np.arange(1, len(MODELS)+1, dtype=np.float64)

    fig: Figure = cast(Figure, plt.figure(figsize=(6.6, 6.2)))  # more square
    ax: Axes = cast(Axes, fig.add_subplot(1, 1, 1))
    violin_quartile_jitter(
        ax, m_list, x, colors,
        ylabel="m_anchor (tempo slope)",
        title=f"External 25°C test: tempo slope distribution (n={n_emb} embryos)",
        jitter=True
    )
    ax.axhline(1.0, color="#111111", linestyle="--", linewidth=1.1, alpha=0.55)
    save_both(fig, outdir / "Fig3_EXT_m_anchor", dpi=dpi)
    plt.close(fig)

def fig3_ext_rmse_resid(outroot: Path, outdir: Path, dpi: int) -> None:
    import matplotlib.pyplot as plt
    r_list: list[FloatArray] = []
    for m in MODELS:
        p = outroot / "EXT25C_TEST" / m / "embryo.csv"
        ensure(p)
        r_list.append(read_csv_col(p, "rmse_resid"))

    colors = [COLORS[m] for m in MODELS]
    x: FloatArray = np.arange(1, len(MODELS)+1, dtype=np.float64)

    fig: Figure = cast(Figure, plt.figure(figsize=(6.6, 6.2)))  # more square
    ax: Axes = cast(Axes, fig.add_subplot(1, 1, 1))
    violin_quartile_jitter(
        ax, r_list, x, colors,
        ylabel="rmse_resid (hours)",
        title="External 25°C test: stability via fit residual scatter",
        jitter=True
    )
    save_both(fig, outdir / "Fig3_EXT_rmse_resid", dpi=dpi)
    plt.close(fig)

def fig3_delta_m_forest(outroot: Path, outdir: Path, dpi: int) -> None:
    import matplotlib.pyplot as plt

    deltas: list[float] = []
    lo: list[float] = []
    hi: list[float] = []
    for m in MODELS:
        p = outroot / f"CI_{m}_m_anchor.json"
        ensure(p)
        d = read_json(p)
        deltas.append(float(d["delta"]["delta_obs"]))
        lo.append(float(d["delta"]["ci95_low"]))
        hi.append(float(d["delta"]["ci95_high"]))

    # narrative order: Full, No-cons, Meanpool, CNN single
    order = [3, 2, 1, 0]
    labels = [LABELS[i] for i in order]
    colors = [COLORS[MODELS[i]] for i in order]
    dm: FloatArray = np.array([deltas[i] for i in order], dtype=np.float64)
    l: FloatArray = np.array([lo[i] for i in order], dtype=np.float64)
    h: FloatArray = np.array([hi[i] for i in order], dtype=np.float64)

    y: FloatArray = np.arange(len(order), dtype=np.float64)

    fig: Figure = cast(Figure, plt.figure(figsize=(6.6, 6.0)))  # squarer
    ax: Axes = cast(Axes, fig.add_subplot(1, 1, 1))

    for yy, mval, ll, hh, c in zip(y, dm, l, h, colors):
        ax.plot([ll, hh], [yy, yy], color=c, linewidth=3.2, solid_capstyle="round", alpha=0.85)
        ax.scatter([mval], [yy], s=80, color=c, edgecolor="white", linewidth=0.9, zorder=3)
        ax.text(hh, yy, f"  {mval:.3f}", va="center", ha="left", fontsize=9, color="#111111")  # small value label

    ax.axvline(0.0, color="#111111", linestyle="--", linewidth=1.1, alpha=0.65)
    ax.xaxis.grid(True, alpha=0.22)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Δm = mean(m_25C) − mean(m_28.5C)   (95% CI)")
    ax.set_title("Temperature effect size (embryo-bootstrap CI)")
    ax.set_xlim(_nice_xlim_from_ci(l, h, pad=0.18))

    save_both(fig, outdir / "Fig3_delta_m_forest", dpi=dpi)
    plt.close(fig)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--outdir", default="")
    ap.add_argument("--dpi", type=int, default=350)
    args = ap.parse_args()

    set_style()

    outroot = Path(args.outroot)
    ensure(outroot)
    outdir = Path(args.outdir) if args.outdir else (outroot / "figures_jobs")
    outdir.mkdir(parents=True, exist_ok=True)

    for m in MODELS:
        ensure(outroot / "ID28C5_TEST" / m / "summary.json")
        ensure(outroot / "EXT25C_TEST" / m / "embryo.csv")
        ensure(outroot / f"CI_{m}_m_anchor.json")

    fig2_id_ablation(outroot, outdir, args.dpi)
    fig3_ext_m_anchor(outroot, outdir, args.dpi)
    fig3_ext_rmse_resid(outroot, outdir, args.dpi)
    fig3_delta_m_forest(outroot, outdir, args.dpi)

    print("[DONE] saved under:", outdir)

if __name__ == "__main__":
    main()
