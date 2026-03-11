from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def parse_csv_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def load_split_ids(split_path: Path, key: str, limit: int = 0) -> list[str]:
    with split_path.open("r", encoding="utf-8") as f:
        split = json.load(f)
    ids = split.get(key)
    if not isinstance(ids, list):
        raise KeyError(f"Split key {key!r} not found or not a list in {split_path}")
    out = [str(x) for x in ids]
    return out[:limit] if limit > 0 else out


def infer_one(
    *,
    cli_script: Path,
    ckpt: Path,
    input_path: Path,
    out_json: Path,
    clip_len: int,
    img_size: int,
    expect_t: int,
    stride: int,
    device: str,
    amp: bool,
    use_ema: bool,
    batch_size: int,
) -> None:
    cmd = [
        sys.executable,
        str(cli_script),
        "infer",
        "--ckpt",
        str(ckpt),
        "--input_path",
        str(input_path),
        "--out_json",
        str(out_json),
        "--clip_len",
        str(clip_len),
        "--img_size",
        str(img_size),
        "--expect_t",
        str(expect_t),
        "--stride",
        str(stride),
        "--trim",
        "0.2",
        "--device",
        device,
        "--batch_size",
        str(batch_size),
        "--num_workers",
        "0",
        "--mem_profile",
        "lowmem",
    ]
    cmd.append("--amp" if amp else "--no-amp")
    cmd.append("--use_ema" if use_ema else "--no-use_ema")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
