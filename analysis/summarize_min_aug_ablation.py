#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_csv_list(text: str) -> list[str]:
    return [x.strip() for x in str(text).split(",") if x.strip()]


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            setting = str(row.get("setting", "")).strip()
            if setting:
                rows[setting] = row
    return rows


def read_best_val_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "best_epoch": "",
            "best_val_mae": "",
            "best_val_rmse": "",
            "best_val_r2": "",
        }

    best_row: dict[str, str] | None = None
    best_val = float("inf")
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                cur = float(row["val_mae"])
            except Exception:
                continue
            if cur < best_val:
                best_val = cur
                best_row = row

    if best_row is None:
        return {
            "best_epoch": "",
            "best_val_mae": "",
            "best_val_rmse": "",
            "best_val_r2": "",
        }

    return {
        "best_epoch": best_row.get("epoch", ""),
        "best_val_mae": best_row.get("val_mae", ""),
        "best_val_rmse": best_row.get("val_rmse", ""),
        "best_val_r2": best_row.get("val_r2", ""),
    }


def fmt(x: Any, digits: int = 3) -> str:
    if x in {"", None}:
        return ""
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


def rows_to_markdown(rows: list[dict[str, Any]], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize the minimal 5-setting full-model augmentation ablation package."
    )
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--settings", default="baseline_full,no_spatial,no_photometric,no_acquisition,no_temporal_sampling")
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--model", default="full")
    ap.add_argument("--eval_dirname", default="eval_main")
    ap.add_argument("--out_csv", default="")
    ap.add_argument("--out_md", default="")
    args = ap.parse_args()

    outroot = Path(args.outroot)
    settings = parse_csv_list(args.settings)
    datasets = parse_csv_list(args.datasets)
    model = str(args.model)
    eval_dirname = str(args.eval_dirname)

    out_csv = Path(args.out_csv) if args.out_csv else outroot / "min_aug_ablation_summary.csv"
    out_md = Path(args.out_md) if args.out_md else outroot / "min_aug_ablation_summary.md"

    manifest = read_manifest(outroot / "manifest.tsv")

    rows: list[dict[str, Any]] = []
    for setting in settings:
        train_dir = outroot / setting
        best_val = read_best_val_metrics(train_dir / "history.csv")
        mf = manifest.get(setting, {})

        for dataset in datasets:
            summary_fp = train_dir / eval_dirname / dataset / model / "summary.json"
            if not summary_fp.exists():
                continue

            summary = json.loads(summary_fp.read_text(encoding="utf-8"))
            gm = summary.get("global_metrics_points", {})
            fa = summary.get("fit_anchor_T0", {})

            rows.append(
                {
                    "setting": setting,
                    "dataset": dataset,
                    "model": model,
                    "aug_disable_groups": mf.get("aug_disable_groups", ""),
                    "jitter": mf.get("jitter", ""),
                    "best_epoch": best_val["best_epoch"],
                    "best_val_mae": best_val["best_val_mae"],
                    "best_val_rmse": best_val["best_val_rmse"],
                    "best_val_r2": best_val["best_val_r2"],
                    "n_embryos": gm.get("n_embryos", ""),
                    "n_points": gm.get("n_points", ""),
                    "mae_h": gm.get("mae", ""),
                    "rmse_h": gm.get("rmse", ""),
                    "r2_points": gm.get("r2", ""),
                    "m_anchor": fa.get("m", ""),
                    "rmse_resid_h": fa.get("rmse_resid", ""),
                    "max_abs_resid_h": fa.get("max_abs_resid", ""),
                }
            )

    if not rows:
        raise SystemExit(f"No aggregated evaluation summaries found under: {outroot}")

    fieldnames = list(rows[0].keys())
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    pretty_rows: list[dict[str, str]] = []
    for row in rows:
        pretty_rows.append(
            {
                "setting": str(row["setting"]),
                "dataset": str(row["dataset"]),
                "aug_disable_groups": str(row["aug_disable_groups"]),
                "jitter": str(row["jitter"]),
                "best val MAE": fmt(row["best_val_mae"]),
                "test MAE (h)": fmt(row["mae_h"]),
                "test RMSE (h)": fmt(row["rmse_h"]),
                "test R2": fmt(row["r2_points"]),
                "m_anchor": fmt(row["m_anchor"]),
                "rmse_resid (h)": fmt(row["rmse_resid_h"]),
                "max_abs_resid (h)": fmt(row["max_abs_resid_h"]),
            }
        )

    headers = [
        "setting",
        "dataset",
        "aug_disable_groups",
        "jitter",
        "best val MAE",
        "test MAE (h)",
        "test RMSE (h)",
        "test R2",
        "m_anchor",
        "rmse_resid (h)",
        "max_abs_resid (h)",
    ]
    out_md.write_text(rows_to_markdown(pretty_rows, headers), encoding="utf-8")

    print(f"WROTE: {out_csv}")
    print(f"WROTE: {out_md}")


if __name__ == "__main__":
    main()
