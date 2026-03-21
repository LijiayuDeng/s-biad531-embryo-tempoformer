#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path

from infer_utils import infer_one, load_split_ids, parse_csv_list


def main() -> None:
    ap = argparse.ArgumentParser(description="Run ETF inference across a dataset/model matrix.")
    ap.add_argument("--outroot", default="", help="Output root. Default: runs/paper_eval_<timestamp>")
    ap.add_argument("--datasets", default="ID28C5_TEST,EXT25C_TEST")
    ap.add_argument("--models", default="cnn_single,meanpool,nocons,full")
    ap.add_argument("--clip_len", type=int, default=24)
    ap.add_argument("--img_size", type=int, default=384)
    ap.add_argument("--expect_t", type=int, default=192)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--amp", type=int, default=1)
    ap.add_argument("--use_ema", type=int, default=1)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--force", type=int, default=0)
    ap.add_argument("--proc_28c5", default="")
    ap.add_argument("--proc_25c", default="")
    ap.add_argument("--split_28c5", default="")
    ap.add_argument("--split_25c", default="")
    ap.add_argument("--proc_28c5_sbiad840", default="")
    ap.add_argument("--proc_25c_sbiad840", default="")
    ap.add_argument("--split_28c5_sbiad840", default="")
    ap.add_argument("--split_25c_sbiad840", default="")
    ap.add_argument("--ckpt_cnn_single", default="")
    ap.add_argument("--ckpt_meanpool", default="")
    ap.add_argument("--ckpt_nocons", default="")
    ap.add_argument("--ckpt_full", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    cli_script = root / "src" / "EmbryoTempoFormer.py"

    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    outroot = Path(args.outroot) if args.outroot else Path("./runs") / f"paper_eval_{stamp}"
    outroot.mkdir(parents=True, exist_ok=True)

    dataset_map: dict[str, tuple[Path, Path, str]] = {}
    if args.proc_28c5 and args.split_28c5:
        dataset_map["ID28C5_TEST"] = (Path(args.proc_28c5), Path(args.split_28c5), "test")
    if args.proc_25c and args.split_25c:
        dataset_map["EXT25C_TEST"] = (Path(args.proc_25c), Path(args.split_25c), "test")
    if args.proc_28c5_sbiad840 and args.split_28c5_sbiad840:
        dataset_map["SBIAD840_28C5_TEST"] = (
            Path(args.proc_28c5_sbiad840),
            Path(args.split_28c5_sbiad840),
            "test",
        )
    if args.proc_25c_sbiad840 and args.split_25c_sbiad840:
        dataset_map["SBIAD840_25C_TEST"] = (
            Path(args.proc_25c_sbiad840),
            Path(args.split_25c_sbiad840),
            "test",
        )
    ckpt_map: dict[str, Path] = {}
    if args.ckpt_cnn_single:
        ckpt_map["cnn_single"] = Path(args.ckpt_cnn_single)
    if args.ckpt_meanpool:
        ckpt_map["meanpool"] = Path(args.ckpt_meanpool)
    if args.ckpt_nocons:
        ckpt_map["nocons"] = Path(args.ckpt_nocons)
    if args.ckpt_full:
        ckpt_map["full"] = Path(args.ckpt_full)

    datasets = parse_csv_list(args.datasets)
    models = parse_csv_list(args.models)

    for ds in datasets:
        if ds not in dataset_map:
            raise SystemExit(
                f"Dataset '{ds}' was requested but its proc/split paths were not provided."
            )
    for model in models:
        if model not in ckpt_map:
            raise SystemExit(
                f"Model '{model}' was requested but its checkpoint path was not provided."
            )

    print(f"[INFO] OUTROOT={outroot}")
    for ds in datasets:
        proc_dir, split_path, split_key = dataset_map[ds]
        ids = load_split_ids(split_path, split_key)
        for model in models:
            out_dir = outroot / ds / model / "json"
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"[RUN] infer {ds} {model}")
            for eid in ids:
                input_path = proc_dir / f"{eid}.npy"
                if not input_path.exists():
                    print(f"[WARN] missing {input_path}")
                    continue
                out_json = out_dir / f"{eid}.json"
                if not args.force and out_json.exists():
                    continue
                infer_one(
                    cli_script=cli_script,
                    ckpt=ckpt_map[model],
                    input_path=input_path,
                    out_json=out_json,
                    clip_len=args.clip_len,
                    img_size=args.img_size,
                    expect_t=args.expect_t,
                    stride=args.stride,
                    device=args.device,
                    amp=bool(args.amp),
                    use_ema=bool(args.use_ema),
                    batch_size=args.batch_size,
                )

    (outroot / "OUTROOT.txt").write_text(f"{outroot}\n", encoding="utf-8")
    print(f"[DONE] infer json in {outroot}")


if __name__ == "__main__":
    main()
