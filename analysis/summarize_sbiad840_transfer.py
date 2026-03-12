#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from EmbryoTempoFormer import TrainConfig, _apply_finetune_policy, build_model  # noqa: E402


def fmt(v: Any, digits: int = 3) -> str:
    if isinstance(v, str):
        return v
    try:
        x = float(v)
    except Exception:
        return str(v)
    return f"{x:.{digits}f}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_summary_row(outroot: Path, dataset: str, model: str) -> dict[str, str]:
    fp = outroot / "sbiad840_external_summary.csv"
    with fp.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    matches = [row for row in rows if row["dataset"] == dataset and row["model"] == model]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one row for {dataset}/{model} in {fp}, got {len(matches)}")
    return matches[0]


def count_split(split_json: Path) -> tuple[int, int, int]:
    obj = read_json(split_json)
    return len(obj["train"]), len(obj["val"]), len(obj["test"])


def build_cfg_from_run_config(run_config: dict[str, Any]) -> TrainConfig:
    train_cfg = dict(run_config["train_config"])
    valid = {f.name for f in fields(TrainConfig)}
    filtered = {k: v for k, v in train_cfg.items() if k in valid}
    return TrainConfig(**filtered)


def count_params(run_dir: Path) -> tuple[int, int]:
    run_cfg = read_json(run_dir / "run_config.json")
    cfg = build_cfg_from_run_config(run_cfg)
    model = build_model(cfg)
    counts = _apply_finetune_policy(model, cfg)
    return int(counts["total_params"]), int(counts["trainable_params"])


def markdown_table(rows: list[dict[str, str]], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(row[h] for h in headers) + " |")
    return "\n".join(out) + "\n"


def infer_model_from_run(run_dir: Path, train_cfg: dict[str, Any]) -> str:
    init_name = Path(train_cfg["init_ckpt"]).name
    for model in ["cnn_single", "meanpool", "nocons", "full"]:
        if model in init_name or model in run_dir.name:
            return model
    raise SystemExit(f"Could not infer model tag from run {run_dir} / init_ckpt {init_name}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize S-BIAD840 fine-tuning runs with parameter counts and external eval metrics."
    )
    ap.add_argument(
        "--experiment",
        action="append",
        nargs=4,
        metavar=("LABEL", "RUN_DIR", "EVAL28_OUTROOT", "EVAL25_OUTROOT"),
        required=True,
        help="One experiment: label, fine-tune run dir, held-out 28C5 eval outroot, 25C external eval outroot",
    )
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--out_md", required=True)
    args = ap.parse_args()

    rows: list[dict[str, Any]] = []
    for label, run_dir_s, eval28_s, eval25_s in args.experiment:
        run_dir = Path(run_dir_s)
        eval28 = Path(eval28_s)
        eval25 = Path(eval25_s)

        run_cfg = read_json(run_dir / "run_config.json")
        train_cfg = run_cfg["train_config"]
        split_json = (ROOT / train_cfg["split_json"]).resolve() if not Path(train_cfg["split_json"]).is_absolute() else Path(train_cfg["split_json"])
        train_n, val_n, test_n = count_split(split_json)
        total_params, trainable_params = count_params(run_dir)
        pct = 100.0 * trainable_params / total_params if total_params else 0.0

        model = infer_model_from_run(run_dir, train_cfg)
        stage = label[len(model) + 1 :] if "_" in label else label
        common = {
            "experiment": label,
            "model": model,
            "stage": stage,
            "fine_tune_dataset": "SBIAD840_28C5",
            "fine_tune_split": split_json.name,
            "train_embryos": train_n,
            "val_embryos": val_n,
            "heldout_28c5_embryos": test_n,
            "total_params": total_params,
            "trainable_params": trainable_params,
            "trainable_pct": pct,
            "init_ckpt": Path(train_cfg["init_ckpt"]).name,
        }

        for dataset, outroot in [
            ("SBIAD840_28C5_TEST", eval28),
            ("SBIAD840_25C_TEST", eval25),
        ]:
            summary = read_summary_row(outroot, dataset, model)
            row = dict(common)
            row.update(
                {
                    "eval_dataset": dataset,
                    "mae_h": float(summary["mae_h"]),
                    "rmse_h": float(summary["rmse_h"]),
                    "r2_points": float(summary["r2_points"]),
                    "m_anchor": float(summary["m_anchor"]),
                    "rmse_resid_h": float(summary["rmse_resid_h"]),
                    "t0_final_median_h": float(summary["t0_final_median_h"]),
                    "m_origin": float(summary["m_origin"]),
                    "origin_resid_mean_h": float(summary["origin_resid_mean_h"]),
                    "origin_resid_sd_h": float(summary["origin_resid_sd_h"]),
                    "origin_r2": float(summary["origin_r2"]),
                    "corr_r2": float(summary["corr_r2"]),
                }
            )
            rows.append(row)

    fieldnames = list(rows[0].keys())
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    pretty_rows: list[dict[str, str]] = []
    for row in rows:
        pretty_rows.append(
            {
                "experiment": str(row["experiment"]),
                "eval_dataset": str(row["eval_dataset"]),
                "params": f"{row['trainable_params']}/{row['total_params']} ({fmt(row['trainable_pct'], 1)}%)",
                "split": f"{row['train_embryos']}/{row['val_embryos']}/{row['heldout_28c5_embryos']}",
                "RMSE (h)": fmt(row["rmse_h"]),
                "m_origin": fmt(row["m_origin"]),
                "origin resid mean±sd (h)": f"{fmt(row['origin_resid_mean_h'])} ± {fmt(row['origin_resid_sd_h'])}",
                "t0 median (h)": fmt(row["t0_final_median_h"]),
                "through-origin line-fit R2": fmt(row["origin_r2"]),
                "corr^2": fmt(row["corr_r2"]),
            }
        )

    headers = [
        "experiment",
        "eval_dataset",
        "params",
        "split",
        "RMSE (h)",
        "m_origin",
        "origin resid mean±sd (h)",
        "t0 median (h)",
        "through-origin line-fit R2",
        "corr^2",
    ]
    out_md.write_text(markdown_table(pretty_rows, headers), encoding="utf-8")

    print(f"WROTE: {out_csv}")
    print(f"WROTE: {out_md}")


if __name__ == "__main__":
    main()
