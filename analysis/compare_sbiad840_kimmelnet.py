#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


KIMMELNET = {
    "SBIAD840_28C5_TEST": {
        "dataset_label": "Dataset C",
        "prediction_error_mean_h": 1.30,
        "prediction_error_sd_h": 5.52,
        "slope": 0.923,
        "r2_line_fit": 0.644,
    },
    "SBIAD840_25C_TEST": {
        "dataset_label": "Dataset D",
        "prediction_error_mean_h": 1.18,
        "prediction_error_sd_h": 5.82,
        "slope": 0.773,
        "r2_line_fit": 0.533,
    },
}


def read_summary_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def fmt(v: Any, digits: int = 3) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compare ETF S-BIAD840 external-domain results against KimmelNet Table 1."
    )
    ap.add_argument("--base_csv", required=True, help="CSV from 36_summarize_sbiad840.sh")
    ap.add_argument(
        "--dense_csv",
        required=True,
        help="CSV from dense cnn_single stride-1 evaluation summary",
    )
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--out_md", required=True)
    args = ap.parse_args()

    base_rows = read_summary_csv(Path(args.base_csv))
    dense_rows = read_summary_csv(Path(args.dense_csv))

    merged: list[dict[str, str]] = []

    for dataset in ["SBIAD840_28C5_TEST", "SBIAD840_25C_TEST"]:
        lit = KIMMELNET[dataset]
        merged.append(
            {
                "dataset": dataset,
                "source": f"KimmelNet {lit['dataset_label']}",
                "protocol": "paper dense single-image",
                "RMSE (h)": "NA",
                "m_anchor": "NA",
                "rmse_resid (h)": "NA",
                "t0 median (h)": "NA",
                "m_origin": fmt(lit["slope"]),
                "origin resid mean±sd (h)": f"{fmt(lit['prediction_error_mean_h'])} ± {fmt(lit['prediction_error_sd_h'])}",
                "through-origin line-fit R2": fmt(lit["r2_line_fit"]),
                "corr^2": "-",
            }
        )

        for row in base_rows:
            if row["dataset"] != dataset:
                continue
            merged.append(
                {
                    "dataset": dataset,
                    "source": f"ETF {row['model']}",
                    "protocol": "current ETF windowing",
                    "RMSE (h)": fmt(row["rmse_h"]),
                    "m_anchor": fmt(row["m_anchor"]),
                    "rmse_resid (h)": fmt(row["rmse_resid_h"]),
                    "t0 median (h)": fmt(row["t0_final_median_h"]),
                    "m_origin": fmt(row["m_origin"]),
                    "origin resid mean±sd (h)": f"{fmt(row['origin_resid_mean_h'])} ± {fmt(row['origin_resid_sd_h'])}",
                    "through-origin line-fit R2": fmt(row["origin_r2"]),
                    "corr^2": fmt(row["corr_r2"]),
                }
            )

        for row in dense_rows:
            if row["dataset"] != dataset:
                continue
            merged.append(
                {
                    "dataset": dataset,
                    "source": "ETF cnn_single dense",
                    "protocol": "clip_len=1, stride=1",
                    "RMSE (h)": fmt(row["rmse_h"]),
                    "m_anchor": fmt(row["m_anchor"]),
                    "rmse_resid (h)": fmt(row["rmse_resid_h"]),
                    "t0 median (h)": fmt(row["t0_final_median_h"]),
                    "m_origin": fmt(row["m_origin"]),
                    "origin resid mean±sd (h)": f"{fmt(row['origin_resid_mean_h'])} ± {fmt(row['origin_resid_sd_h'])}",
                    "through-origin line-fit R2": fmt(row["origin_r2"]),
                    "corr^2": fmt(row["corr_r2"]),
                }
            )

    fieldnames = [
        "dataset",
        "source",
        "protocol",
        "RMSE (h)",
        "m_anchor",
        "rmse_resid (h)",
        "t0 median (h)",
        "m_origin",
        "origin resid mean±sd (h)",
        "through-origin line-fit R2",
        "corr^2",
    ]

    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    md_lines = ["| " + " | ".join(fieldnames) + " |", "|" + "|".join(["---"] * len(fieldnames)) + "|"]
    for row in merged:
        md_lines.append("| " + " | ".join(row[k] for k in fieldnames) + " |")
    out_md.write_text("\n".join(md_lines) + "\n")

    print(f"WROTE: {out_csv}")
    print(f"WROTE: {out_md}")


if __name__ == "__main__":
    main()
