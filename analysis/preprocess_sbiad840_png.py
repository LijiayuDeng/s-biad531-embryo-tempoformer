#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from preprocess_utils import jdump, pad_or_trim_T, percentile_clip_to_u8, resize_stack_u8, save_proc_npy


FILE_RE = re.compile(r"^(?P<prefix>.+?\.nd2)-(?P<embryo>\d+)-(?P<timeidx>\d+)\.png$")
DATASET_MAP = {
    "Dataset_C": "28C5",
    "Dataset_D": "25C",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Convert S-BIAD840 Princeton_Data PNG time folders into ETF processed .npy stacks."
    )
    ap.add_argument(
        "--src_root",
        required=True,
        help="Directory containing Dataset_C and Dataset_D, e.g. .../Files/Princeton_Data",
    )
    ap.add_argument("--out_root", required=True, help="Output root for processed dirs and test-only split JSONs.")
    ap.add_argument(
        "--align_start_hpf",
        type=float,
        default=4.5,
        help="Drop earlier frames so the first kept frame is this hpf (default: 4.5).",
    )
    ap.add_argument("--expect_t", type=int, default=192)
    ap.add_argument("--img_size", type=int, default=384)
    ap.add_argument("--p_lo", type=float, default=1.0)
    ap.add_argument("--p_hi", type=float, default=99.0)
    ap.add_argument(
        "--pad_to_expect",
        type=int,
        default=0,
        help="If 1, pad/trim time axis to expect_t. Default 0 keeps native post-alignment T.",
    )
    ap.add_argument("--limit", type=int, default=0, help="Optional embryo limit per dataset for smoke tests.")
    return ap.parse_args()


def sorted_time_dirs(ds_dir: Path) -> list[Path]:
    return sorted([p for p in ds_dir.iterdir() if p.is_dir()], key=lambda p: float(p.name))


def index_folder(folder: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for p in folder.glob("*.png"):
        m = FILE_RE.match(p.name)
        if m is None:
            continue
        embryo_idx = int(m.group("embryo"))
        if embryo_idx in out:
            raise ValueError(f"duplicate embryo index {embryo_idx} in {folder}")
        out[embryo_idx] = p
    return out


def read_png_gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"))


def build_stack(keep_dirs: list[Path], embryo_idx: int) -> tuple[np.ndarray, list[str]]:
    frames: list[np.ndarray] = []
    src_names: list[str] = []
    for d in keep_dirs:
        fp = index_folder(d).get(embryo_idx)
        if fp is None:
            raise FileNotFoundError(f"missing embryo {embryo_idx} in {d}")
        frames.append(read_png_gray(fp))
        src_names.append(fp.name)
    return np.stack(frames, axis=0), src_names


def preprocess_external_stack(
    raw: np.ndarray,
    *,
    img_size: int,
    p_lo: float,
    p_hi: float,
    expect_t: int,
    pad_to_expect: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    u8, clip_meta = percentile_clip_to_u8(raw, p_lo=p_lo, p_hi=p_hi)
    u8 = resize_stack_u8(u8, img_size=img_size)
    t_meta: dict[str, Any]
    if pad_to_expect:
        u8, t_meta = pad_or_trim_T(u8, expect_t=expect_t)
    else:
        t_meta = {"orig_T": int(u8.shape[0]), "expect_t": int(expect_t), "action": "keep_native"}
    return u8, {"clip": clip_meta, "t": t_meta, "img_size": int(img_size)}


def main() -> None:
    args = parse_args()
    src_root = Path(args.src_root)
    out_root = Path(args.out_root)
    split_root = out_root / "splits"
    split_root.mkdir(parents=True, exist_ok=True)

    for src_name, tag in DATASET_MAP.items():
        ds_dir = src_root / src_name
        if not ds_dir.exists():
            raise FileNotFoundError(ds_dir)

        time_dirs = sorted_time_dirs(ds_dir)
        if not time_dirs:
            raise ValueError(f"no time directories in {ds_dir}")
        keep_dirs = [p for p in time_dirs if float(p.name) >= args.align_start_hpf]
        if not keep_dirs:
            raise ValueError(f"no frames at/after {args.align_start_hpf} hpf in {ds_dir}")

        embryo_ids = sorted(index_folder(keep_dirs[0]).keys())
        for d in keep_dirs[1:]:
            embryo_ids = sorted(set(embryo_ids) & set(index_folder(d).keys()))
        if not embryo_ids:
            raise ValueError(f"no consistent embryo ids across kept dirs in {ds_dir}")

        proc_dir = out_root / f"processed_{tag}_sbiad840"
        proc_dir.mkdir(parents=True, exist_ok=True)
        meta_all: dict[str, Any] = {}
        out_ids: list[str] = []

        n_done = 0
        for embryo_idx in embryo_ids:
            if args.limit > 0 and n_done >= args.limit:
                break

            raw, src_names = build_stack(keep_dirs, embryo_idx)
            proc, meta = preprocess_external_stack(
                raw,
                img_size=args.img_size,
                p_lo=args.p_lo,
                p_hi=args.p_hi,
                expect_t=args.expect_t,
                pad_to_expect=bool(args.pad_to_expect),
            )
            eid = f"SBIAD840_{tag}_E{embryo_idx:03d}"
            save_proc_npy(proc_dir, eid, proc)
            meta_all[eid] = {
                "source_dataset": src_name,
                "source_embryo_index": embryo_idx,
                "orig_time_start_hpf": float(time_dirs[0].name),
                "orig_time_end_hpf": float(time_dirs[-1].name),
                "kept_time_start_hpf": float(keep_dirs[0].name),
                "kept_time_end_hpf": float(keep_dirs[-1].name),
                "n_time_dirs_total": len(time_dirs),
                "n_time_dirs_kept": len(keep_dirs),
                "dropped_pre_frames": len(time_dirs) - len(keep_dirs),
                "raw_shape": list(raw.shape),
                "first_source_file": src_names[0],
                "last_source_file": src_names[-1],
                "preprocess": meta,
            }
            out_ids.append(eid)
            n_done += 1

        jdump(
            {
                "meta": meta_all,
                "args": {
                    "src_root": str(src_root),
                    "dataset_dir": str(ds_dir),
                    "align_start_hpf": args.align_start_hpf,
                    "expect_t": args.expect_t,
                    "img_size": args.img_size,
                    "p_lo": args.p_lo,
                    "p_hi": args.p_hi,
                    "pad_to_expect": bool(args.pad_to_expect),
                    "limit": args.limit,
                },
            },
            proc_dir / "preprocess_meta.json",
        )

        split_payload = {
            "train": [],
            "val": [],
            "test": out_ids,
            "meta": {
                "source_dataset": src_name,
                "condition_tag": tag,
                "test_only_external_domain": True,
                "align_start_hpf": args.align_start_hpf,
                "dt_h": 0.25,
            },
        }
        split_path = split_root / f"{tag}_sbiad840_test.json"
        jdump(split_payload, split_path)
        print(f"[done] {src_name} -> {proc_dir} ({len(out_ids)} embryos); split={split_path}")


if __name__ == "__main__":
    main()
