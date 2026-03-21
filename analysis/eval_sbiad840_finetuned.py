#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from env_utils import get_setting, load_dotenv_defaults, resolve_path


def run_checked(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Evaluate a fine-tuned checkpoint on Princeton S-BIAD840 datasets by "
            "reusing the standard inference, aggregation, and external-summary pipeline."
        )
    )
    ap.add_argument("--ft_ckpt", default="", help="Fine-tuned checkpoint to evaluate")
    ap.add_argument("--model", required=True, choices=["cnn_single", "meanpool", "nocons", "full"])
    ap.add_argument("--outroot", required=True, help="Output root for the evaluation run")
    ap.add_argument(
        "--datasets",
        default="SBIAD840_28C5_TEST,SBIAD840_25C_TEST",
        help="Comma-separated Princeton datasets to evaluate",
    )
    ap.add_argument("--device", default="")
    ap.add_argument("--amp", type=int, default=-1)
    ap.add_argument("--use_ema", type=int, default=-1)
    ap.add_argument("--force_infer", type=int, default=1, choices=[0, 1])
    ap.add_argument("--batch_size", type=int, default=0)
    ap.add_argument("--clip_len", type=int, default=0)
    ap.add_argument("--img_size", type=int, default=0)
    ap.add_argument("--expect_t", type=int, default=0)
    ap.add_argument("--stride", type=int, default=0)
    ap.add_argument("--dt", type=float, default=-1.0)
    ap.add_argument("--t0", type=float, default=-1.0)
    ap.add_argument("--proc_28c5_sbiad840", default="")
    ap.add_argument("--proc_25c_sbiad840", default="")
    ap.add_argument("--split_28c5_sbiad840", default="")
    ap.add_argument("--split_25c_sbiad840", default="")
    ap.add_argument("--out_csv", default="", help="Optional explicit summary CSV path")
    ap.add_argument("--out_md", default="", help="Optional explicit summary Markdown path")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    dotenv_defaults = load_dotenv_defaults(repo_root)

    ft_ckpt = args.ft_ckpt or get_setting("FT_CKPT", dotenv_defaults)
    if not ft_ckpt:
        raise SystemExit(
            "Missing fine-tuned checkpoint: pass --ft_ckpt or set FT_CKPT in environment/.env"
        )

    proc_28 = args.proc_28c5_sbiad840 or get_setting("PROC_28C5_SBIAD840", dotenv_defaults)
    proc_25 = args.proc_25c_sbiad840 or get_setting("PROC_25C_SBIAD840", dotenv_defaults)
    split_28 = args.split_28c5_sbiad840 or get_setting("SPLIT_28C5_SBIAD840", dotenv_defaults)
    split_25 = args.split_25c_sbiad840 or get_setting("SPLIT_25C_SBIAD840", dotenv_defaults)
    for name, value in {
        "PROC_28C5_SBIAD840": proc_28,
        "PROC_25C_SBIAD840": proc_25,
        "SPLIT_28C5_SBIAD840": split_28,
        "SPLIT_25C_SBIAD840": split_25,
    }.items():
        if not value:
            raise SystemExit(f"Missing required dataset path: {name}")

    outroot = resolve_path(args.outroot, repo_root)
    out_csv = resolve_path(args.out_csv, repo_root) if args.out_csv else str(Path(outroot) / "sbiad840_external_summary.csv")
    out_md = resolve_path(args.out_md, repo_root) if args.out_md else str(Path(outroot) / "sbiad840_external_summary.md")

    def pick_str(cli: str, env_name: str, default: str) -> str:
        return cli or get_setting(env_name, dotenv_defaults, default)

    def pick_int(cli: int, env_name: str, default: int) -> int:
        if cli > 0:
            return cli
        return int(get_setting(env_name, dotenv_defaults, str(default)))

    def pick_bool(cli: int, env_name: str, default: int) -> int:
        if cli in (0, 1):
            return cli
        return int(get_setting(env_name, dotenv_defaults, str(default)))

    def pick_float(cli: float, env_name: str, default: float) -> float:
        if cli >= 0:
            return cli
        return float(get_setting(env_name, dotenv_defaults, str(default)))

    device = pick_str(args.device, "DEVICE", "cuda")
    amp = pick_bool(args.amp, "AMP", 1)
    use_ema = pick_bool(args.use_ema, "USE_EMA", 1)
    batch_size = pick_int(args.batch_size, "BATCH_SIZE", 64)
    clip_len = pick_int(args.clip_len, "CLIP_LEN", 24)
    img_size = pick_int(args.img_size, "IMG_SIZE", 384)
    expect_t = pick_int(args.expect_t, "EXPECT_T", 192)
    stride = pick_int(args.stride, "STRIDE", 8)
    dt = pick_float(args.dt, "DT_H", 0.25)
    t0 = pick_float(args.t0, "T0_HPF", 4.5)

    infer_cmd = [
        sys.executable,
        "analysis/run_infer_matrix.py",
        "--outroot",
        outroot,
        "--force",
        str(args.force_infer),
        "--datasets",
        args.datasets,
        "--models",
        args.model,
        "--clip_len",
        str(clip_len),
        "--img_size",
        str(img_size),
        "--expect_t",
        str(expect_t),
        "--stride",
        str(stride),
        "--device",
        device,
        "--amp",
        str(amp),
        "--use_ema",
        str(use_ema),
        "--batch_size",
        str(batch_size),
        "--proc_28c5_sbiad840",
        resolve_path(proc_28, repo_root),
        "--proc_25c_sbiad840",
        resolve_path(proc_25, repo_root),
        "--split_28c5_sbiad840",
        resolve_path(split_28, repo_root),
        "--split_25c_sbiad840",
        resolve_path(split_25, repo_root),
        f"--ckpt_{args.model}",
        resolve_path(ft_ckpt, repo_root),
    ]

    agg_cmd = [
        sys.executable,
        "analysis/aggregate_matrix.py",
        "--outroot",
        outroot,
        "--datasets",
        args.datasets,
        "--models",
        args.model,
        "--dt",
        str(dt),
        "--t0",
        str(t0),
        "--force",
        "1",
    ]

    summary_cmd = [
        sys.executable,
        "analysis/summarize_sbiad840_external.py",
        "--outroot",
        outroot,
        "--datasets",
        args.datasets,
        "--models",
        args.model,
        "--out_csv",
        out_csv,
        "--out_md",
        out_md,
    ]

    print(f"[INFO] FT_CKPT={resolve_path(ft_ckpt, repo_root)}")
    print(f"[INFO] MODEL={args.model}")
    print(f"[INFO] DATASETS={args.datasets}")
    print(f"[INFO] OUTROOT={outroot}")
    run_checked(infer_cmd, repo_root)
    run_checked(agg_cmd, repo_root)
    run_checked(summary_cmd, repo_root)
    print(f"[DONE] Fine-tuned S-BIAD840 evaluation written under: {outroot}")


if __name__ == "__main__":
    main()
