#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from infer_utils import infer_one, load_split_ids, parse_csv_list


def aggregate_one(cli_script: Path, json_dir: Path, out_dir: Path, dt: float, t0: float) -> None:
    cmd = [
        sys.executable,
        str(cli_script),
        "--json_dir",
        str(json_dir),
        "--out_dir",
        str(out_dir),
        "--dt",
        str(dt),
        "--t0",
        str(t0),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def count_json(json_dir: Path) -> int:
    return len(list(json_dir.glob("*.json")))


def collect_summary_rows(outroot: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lp in sorted(outroot.glob("L*/")):
        try:
            clip_len = int(lp.name[1:])
        except Exception:
            continue
        for ds in sorted(lp.iterdir()):
            if not ds.is_dir():
                continue
            for model_dir in sorted(ds.iterdir()):
                if not model_dir.is_dir():
                    continue
                summ = model_dir / "summary.json"
                if not summ.exists():
                    continue
                obj = json.loads(summ.read_text(encoding="utf-8"))
                gm = obj.get("global_metrics_points", {})
                fa = obj.get("fit_anchor_T0", {})
                rows.append(
                    {
                        "clip_len": clip_len,
                        "dataset": ds.name,
                        "model": model_dir.name,
                        "n_embryos": gm.get("n_embryos"),
                        "n_points": gm.get("n_points"),
                        "mae": gm.get("mae"),
                        "rmse": gm.get("rmse"),
                        "r2": gm.get("r2"),
                        "m_anchor_global": fa.get("m"),
                        "rmse_resid": fa.get("rmse_resid"),
                        "max_abs_resid": fa.get("max_abs_resid"),
                    }
                )
    return rows


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "clip_len",
        "dataset",
        "model",
        "n_embryos",
        "n_points",
        "mae",
        "rmse",
        "r2",
        "m_anchor_global",
        "rmse_resid",
        "max_abs_resid",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run fixed-checkpoint clip-length sensitivity analysis.")
    ap.add_argument("--outroot", default="", help="Default: runs/cliplen_sensitivity_<timestamp>")
    ap.add_argument("--clip_lens", default="4,12,24")
    ap.add_argument("--models", default="full")
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--dt_h", type=float, default=0.25)
    ap.add_argument("--t0_hpf", type=float, default=4.5)
    ap.add_argument("--img_size", type=int, default=384)
    ap.add_argument("--expect_t", type=int, default=192)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--amp", type=int, default=1)
    ap.add_argument("--use_ema", type=int, default=1)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--max_eids", type=int, default=0)
    ap.add_argument("--force", type=int, default=0)
    ap.add_argument("--proc_28c5", required=True)
    ap.add_argument("--proc_25c", required=True)
    ap.add_argument("--split_28c5", required=True)
    ap.add_argument("--split_25c", required=True)
    ap.add_argument("--ckpt_cnn_single", required=True)
    ap.add_argument("--ckpt_meanpool", required=True)
    ap.add_argument("--ckpt_nocons", required=True)
    ap.add_argument("--ckpt_full", required=True)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    infer_cli = root / "src" / "EmbryoTempoFormer.py"
    aggregate_cli = root / "analysis" / "aggregate_kimmel.py"

    outroot = Path(args.outroot) if args.outroot else Path("./runs") / f"cliplen_sensitivity_{time.strftime('%Y%m%d_%H%M%S')}"
    outroot.mkdir(parents=True, exist_ok=True)

    dataset_map = {
        "ID28C5_TEST": (Path(args.proc_28c5), Path(args.split_28c5), "test"),
        "EXT25C_TEST": (Path(args.proc_25c), Path(args.split_25c), "test"),
    }
    ckpt_map = {
        "cnn_single": Path(args.ckpt_cnn_single),
        "meanpool": Path(args.ckpt_meanpool),
        "nocons": Path(args.ckpt_nocons),
        "full": Path(args.ckpt_full),
    }

    clip_lens = [int(x) for x in parse_csv_list(args.clip_lens)]
    datasets = parse_csv_list(args.datasets)
    models = parse_csv_list(args.models)

    print(f"[INFO] OUTROOT={outroot}")
    print(f"[INFO] clip_lens={args.clip_lens} models={args.models} datasets={args.datasets}")
    print(f"[INFO] stride={args.stride} dt_h={args.dt_h} t0_hpf={args.t0_hpf} force={args.force} max_eids={args.max_eids}")

    for L in clip_lens:
        tagL = f"L{L:02d}"
        for ds in datasets:
            if ds not in dataset_map:
                raise KeyError(f"Unknown dataset tag: {ds}")
            proc_dir, split_path, split_key = dataset_map[ds]
            ids = load_split_ids(split_path, split_key, args.max_eids)
            for model in models:
                if model not in ckpt_map:
                    raise KeyError(f"Unknown model tag: {model}")
                json_dir = outroot / tagL / ds / model / "json"
                out_dir = outroot / tagL / ds / model
                json_dir.mkdir(parents=True, exist_ok=True)
                out_dir.mkdir(parents=True, exist_ok=True)
                print(f"[RUN] clip_len={L} dataset={ds} model={model}")
                for eid in ids:
                    input_path = proc_dir / f"{eid}.npy"
                    if not input_path.exists():
                        print(f"[WARN] missing {input_path}")
                        continue
                    out_json = json_dir / f"{eid}.json"
                    if not args.force and out_json.exists():
                        continue
                    infer_one(
                        cli_script=infer_cli,
                        ckpt=ckpt_map[model],
                        input_path=input_path,
                        out_json=out_json,
                        clip_len=L,
                        img_size=args.img_size,
                        expect_t=args.expect_t,
                        stride=args.stride,
                        device=args.device,
                        amp=bool(args.amp),
                        use_ema=bool(args.use_ema),
                        batch_size=args.batch_size,
                    )

                if not args.force and (out_dir / "summary.json").exists():
                    continue
                if count_json(json_dir) == 0:
                    print(f"[WARN] no json files in {json_dir}; skip aggregate")
                    continue
                aggregate_one(aggregate_cli, json_dir, out_dir, args.dt_h, args.t0_hpf)

    rows = collect_summary_rows(outroot)
    write_summary_csv(outroot / "cliplen_summary.csv", rows)
    print(f"WROTE: {outroot / 'cliplen_summary.csv'}")
    print(f"[DONE] clip-length sensitivity outputs under: {outroot}")


if __name__ == "__main__":
    main()
