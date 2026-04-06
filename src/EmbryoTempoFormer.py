# -*- coding: utf-8 -*-
"""
EmbryoTempoFormer
=================

A single-file, reproducible reference implementation for zebrafish embryo
developmental "age" estimation from brightfield time-lapse stacks.

This script intentionally keeps a minimal dependency footprint and exposes a
single CLI with five subcommands:

  1) preprocess
     Convert raw OME-TIF stacks into fixed-shape uint8 `.npy` tensors:
       - intensity normalized by percentile clipping (p_lo/p_hi)
       - resized to img_size x img_size
       - padded/trimmed along time to expect_t frames

  2) make_split
     Create a JSON split file listing embryo IDs (stems of `.npy` files):
       {"train":[...], "val":[...], "test":[...]}

  3) train
     Train a clip-based model with pair sampling:
       - absolute loss: L1/SmoothL1 on predicted offset time (hpf)
       - temporal-difference consistency: constrain (p2 - p1) to match known
         sampling interval DT * (s2 - s1) within the same embryo (optional)

  4) eval
     Clip-level evaluation on the "val" split using a deterministic dataset.
     NOTE: clip-level samples are highly correlated within embryo; use embryo-
     level statistics for inferential claims in a manuscript.

  5) infer
     Embryo-level inference for a single `.npy` or `.tif/.tiff` stack by sliding
     windows across the full sequence:
       - for each window start s: predict offset(s)
       - convert to t0_hat(s) = offset(s) - DT*s
       - aggregate across s with trimmed mean -> t0_final
       - return {t0_final, starts, t0_hats, metrics, source, ...} as JSON

Engineering / reproducibility notes
-----------------------------------
- All paths can be relative. Interpret them relative to the current working
  directory (cwd). Avoid hard-coded /mnt/... paths in release scripts.
- `argparse` subparsers store a non-serializable function object in `args.func`.
  We must drop it when writing preprocess/run metadata JSON.
- Checkpoints store both raw weights and EMA shadow weights (if enabled).
  Use `--use_ema` in eval/infer to load EMA weights for consistent reporting.

Defaults
--------
- T0_HPF = 4.5 and DT_H = 0.25 correspond to S-BIAD531-like staging where
  frames are sampled every 15 minutes starting at 4.5 hpf.
  If your acquisition differs, adjust DT_H/T0_HPF accordingly *in analysis*.

This file is long by design to make it easy to ship as a single script in a
repository release / supplementary material.

Authoring note: "paper-level" docstrings focus on:
  - what each component does, shapes, and assumptions
  - statistical pitfalls (pseudo-replication)
  - why certain engineering choices exist (OOM mitigation, mem profiles)

"""

from __future__ import annotations

import os
import re
import csv
import json
import math
import time
import random
import argparse
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import Dataset, DataLoader, get_worker_info
from torch.utils.data.distributed import DistributedSampler
from torch.utils.checkpoint import checkpoint, checkpoint_sequential

try:
    import tifffile
except Exception:
    tifffile = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import torchvision.transforms.functional as TVF
except Exception:
    TVF = None

from preprocess_utils import jdump, pad_or_trim_T, percentile_clip_to_u8, preprocess_stack, resize_stack_u8, save_proc_npy


# ---------------------------------------------------------------------
# Public identity
# ---------------------------------------------------------------------
MODEL_NAME = "EmbryoTempoFormer"
DEFAULT_RUNS_DIRNAME = "runs"

# time label (hours post fertilization)
T0_HPF = 4.5
DT_H = 0.25

EXPECT_T_DEFAULT = 192
DEFAULT_CLIP_LEN = 24


# ---------------------------------------------------------------------
# Manual exclusions (dataset-specific)
# ---------------------------------------------------------------------
EXCLUDE_KEYS = {
    "FishDev_WT_01_1-A3", "FishDev_WT_01_1-B3", "FishDev_WT_01_1-C3", "FishDev_WT_01_1-D3",
    "FishDev_WT_01_1-E3", "FishDev_WT_01_1-F3", "FishDev_WT_01_1-G3", "FishDev_WT_01_1-H3",
    "FishDev_WT_02_1-A1", "FishDev_WT_02_1-B1", "FishDev_WT_02_1-C1", "FishDev_WT_02_1-D1",
    "FishDev_WT_02_1-E1", "FishDev_WT_02_1-F1", "FishDev_WT_02_1-G1", "FishDev_WT_02_1-H1",
    "FishDev_WT_03_1-A2", "FishDev_WT_03_1-B2", "FishDev_WT_03_1-C2", "FishDev_WT_03_1-D2",
    "FishDev_WT_03_1-E2", "FishDev_WT_03_1-F2", "FishDev_WT_03_1-G2", "FishDev_WT_03_1-H2",
    "FishDev_WT_04_1-A2", "FishDev_WT_04_1-B2", "FishDev_WT_04_1-C2", "FishDev_WT_04_1-D2",
    "FishDev_WT_04_1-E2", "FishDev_WT_04_1-F2", "FishDev_WT_04_1-G2",
    "FishDev_WT_05_1-A4", "FishDev_WT_05_1-B4", "FishDev_WT_05_1-C4", "FishDev_WT_05_1-D4",
    "FishDev_WT_05_1-E4", "FishDev_WT_05_1-F4", "FishDev_WT_05_1-G4", "FishDev_WT_05_1-H4",
}


# ---------------------------------------------------------------------
# Memory profiles
# ---------------------------------------------------------------------
MEM_PROFILES = {
    # Fastest but most memory-hungry.
    "fast":     dict(frame_chunk=16, ckpt_frame=False, ckpt_cnn=False, ckpt_segments=1),

    # Trade memory for compute using checkpointing inside CNN blocks.
    "balanced": dict(frame_chunk=8,  ckpt_frame=False, ckpt_cnn=True,  ckpt_segments=2),

    # Most effective OOM fix: checkpoint the *whole* frame encoder per chunk.
    # This avoids keeping the entire 24-frame computation graph.
    "lowmem":   dict(frame_chunk=4,  ckpt_frame=True,  ckpt_cnn=False, ckpt_segments=1),

    # Extreme memory saving: process one frame at a time (slow but safe).
    "ultra":    dict(frame_chunk=1,  ckpt_frame=True,  ckpt_cnn=False, ckpt_segments=1),
}


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def now_str() -> str:
    """Return local timestamp string for logs/metadata."""
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def jload(path: str | Path) -> Any:
    """Load JSON from `path`."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _jsonable_args(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert argparse.Namespace to a JSON-serializable dict.

    Why needed:
    - argparse subparsers usually set `args.func = <callable>` via set_defaults().
    - a Python function object is not JSON serializable.
    """
    d = dict(vars(args))
    d.pop("func", None)
    return d


def _default_out_dir_for_nontrain() -> str:
    """
    For eval/infer we still reconstruct a TrainConfig, which expects an out_dir.
    Use a relative default rooted at cwd.
    """
    return str(Path.cwd() / DEFAULT_RUNS_DIRNAME)


def dump_run_config(out_dir: Path, cfg: "TrainConfig") -> None:
    """
    Save a human-readable run_config.json into out_dir.

    This is a lightweight provenance record:
    - training config
    - memory profile details
    - augmentation settings actually used for training
    - basic environment info (torch/cuda/cudnn)
    """
    mp = MEM_PROFILES.get(cfg.mem_profile, MEM_PROFILES["balanced"])
    aug = build_aug_params(cfg.aug_disable_groups)
    env = {
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "device_count": torch.cuda.device_count(),
        "gpu0": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    payload = {
        "train_config": dataclasses.asdict(cfg),
        "mem_profile_detail": mp,
        "augment": dataclasses.asdict(aug),
        "augment_disable_groups": sorted(parse_csv_groups(cfg.aug_disable_groups)),
        "env": env,
    }
    jdump(payload, out_dir / "run_config.json")


def _short_key_from_eid(eid: str) -> str:
    """
    Convert a full embryo id (file stem) to a short plate-well key.

    Some datasets encode well info in different patterns; this helper normalizes:
      FishDev_WT_01_1_MMStack_A1-Site_0.ome  -> FishDev_WT_01_1-A1
    """
    m = re.search(r"^(?P<prefix>.+?)_MMStack_(?P<well>[A-H]\d{1,2})\b", eid)
    if m:
        return f"{m.group('prefix')}-{m.group('well')}"
    m2 = re.search(r"^(?P<prefix>.+?)_(?P<well>[A-H]\d{1,2})\b", eid)
    if m2:
        return f"{m2.group('prefix')}-{m2.group('well')}"
    return eid


def is_excluded(eid: str) -> bool:
    """Return True if an embryo id matches exclusion rules."""
    sk = _short_key_from_eid(eid)
    return (eid in EXCLUDE_KEYS) or (sk in EXCLUDE_KEYS)


def filter_excluded(ids: Sequence[str]) -> List[str]:
    """Filter a list of ids by EXCLUDE_KEYS."""
    return [x for x in ids if not is_excluded(x)]


def seed_all(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch RNGs for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def seed_worker(worker_id: int) -> None:
    """
    DataLoader worker initialization.

    Ensures each worker has a different deterministic seed. Also notifies datasets
    that implement `reseed(seed)`.
    """
    worker_seed = (torch.initial_seed() + worker_id) % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    info = get_worker_info()
    if info is not None and hasattr(info.dataset, "reseed"):
        info.dataset.reseed(int(worker_seed))


def ensure_device(device: str) -> torch.device:
    """
    Convert device string to torch.device.

    device="auto" chooses CUDA if available else CPU.
    """
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def mae_rmse_np(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute MAE and RMSE (in the same units as input, here hours)."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    err = y_pred - y_true
    return {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err**2)))}


def gn_groups(ch: int, max_groups: int = 8) -> int:
    """Choose a GroupNorm group count that divides `ch` (<= max_groups)."""
    ch = int(ch)
    for g in range(min(max_groups, ch), 0, -1):
        if ch % g == 0:
            return g
    return 1


def checkpoint_seq(seq: nn.Sequential, segments: int, x: torch.Tensor) -> torch.Tensor:
    """
    Checkpoint a sequential module to save memory.

    Uses non-reentrant checkpoint when available (PyTorch>=2.0).
    """
    segs = max(1, min(int(segments), len(seq)))
    try:
        return checkpoint_sequential(seq, segs, x, use_reentrant=False)
    except TypeError:
        return checkpoint_sequential(seq, segs, x)


def checkpoint_call(fn, *args):
    """Checkpoint a single function call (non-reentrant when available)."""
    try:
        return checkpoint(fn, *args, use_reentrant=False)
    except TypeError:
        return checkpoint(fn, *args)


# ---------------------------------------------------------------------
# DDP helpers
# ---------------------------------------------------------------------
def ddp_is_enabled() -> bool:
    """Return True if torch.distributed is initialized."""
    return dist.is_available() and dist.is_initialized()


def ddp_rank() -> int:
    """Global rank (0 if not DDP)."""
    return dist.get_rank() if ddp_is_enabled() else 0


def ddp_is_main() -> bool:
    """True for global rank 0."""
    return ddp_rank() == 0


def ddp_local_rank() -> int:
    """Local rank from environment (torchrun sets LOCAL_RANK)."""
    return int(os.environ.get("LOCAL_RANK", "0"))


def ddp_init() -> Tuple[torch.device, bool]:
    """
    Initialize distributed training if launched with torchrun.

    Returns:
      device: torch.device for this process
      ddp: bool flag
    """
    if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
        local_rank = ddp_local_rank()
        if torch.cuda.is_available():
            torch.cuda.set_device(local_rank)
            dist.init_process_group(backend="nccl")
            return torch.device("cuda", local_rank), True
        dist.init_process_group(backend="gloo")
        return torch.device("cpu"), True
    return torch.device("cuda" if torch.cuda.is_available() else "cpu"), False


@torch.no_grad()
def ddp_all_reduce_sum_(t: torch.Tensor) -> torch.Tensor:
    """In-place sum-reduce tensor across processes (no-op if not DDP)."""
    if ddp_is_enabled():
        dist.all_reduce(t, op=dist.ReduceOp.SUM)
    return t


@torch.no_grad()
def ddp_r2_from_stats(sum_y: torch.Tensor, sum_y2: torch.Tensor, sum_err2: torch.Tensor, n: torch.Tensor) -> float:
    """
    Compute R^2 from aggregated stats.

    Uses: SST = sum(y^2) - sum(y)*mean(y)
          R2 = 1 - SSE/SST

    Returns nan if SST is ~0 or n<2.
    """
    eps = 1e-12
    n_val = float(n.item())
    if n_val < 2:
        return float("nan")
    mean = sum_y / (n + eps)
    sst = sum_y2 - (sum_y * mean)
    if abs(float(sst.item())) < 1e-12:
        return float("nan")
    return float((1.0 - (sum_err2 / (sst + eps))).item())


# ---------------------------------------------------------------------
# TIFF I/O + preprocess
# ---------------------------------------------------------------------
def read_tiff_stack(path: str | Path, max_pages: Optional[int] = None) -> np.ndarray:
    """
    Read a TIFF/OME-TIFF as a [T,H,W] numpy array (dtype determined by file).

    Notes
    -----
    - This reads pages sequentially and stacks them in memory.
    - For very large stacks, use max_pages to cap pages (e.g., 192).
    """
    if tifffile is None:
        raise RuntimeError("tifffile not installed")
    with tifffile.TiffFile(str(path)) as tf:
        pages = tf.pages[:max_pages] if max_pages is not None else tf.pages
        arrs = [p.asarray() for p in pages]
    if not arrs:
        raise ValueError(f"Empty TIFF: {path}")
    s0 = arrs[0].shape
    for i, a in enumerate(arrs):
        if a.shape != s0:
            raise ValueError(f"Inconsistent TIFF pages: {s0} vs {a.shape} at {i}")
    return np.stack(arrs, axis=0)


def load_frames_memmap(proc_dir: Path, eid: str) -> np.ndarray:
    """Load processed stack using numpy memmap (read-only) to reduce RAM usage."""
    path = proc_dir / f"{eid}.npy"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return np.load(path, mmap_mode="r")


def load_frames_T(proc_dir: Path, eid: str) -> int:
    """Quickly query the number of frames in an embryo stack."""
    return int(load_frames_memmap(proc_dir, eid).shape[0])


# ---------------------------------------------------------------------
# Augmentations
# ---------------------------------------------------------------------
@dataclass
class AugParams:
    """
    Clip-level augmentation hyperparameters.

    Applied consistently across frames where appropriate (e.g., affine uses
    identical parameters for all frames).
    """
    p_hflip: float = 0.5

    p_affine: float = 0.5
    max_rotate_deg: float = 8.0
    max_translate: float = 0.03
    scale_min: float = 0.97
    scale_max: float = 1.03

    p_gamma: float = 0.5
    gamma_min: float = 0.8
    gamma_max: float = 1.15

    p_contrast: float = 0.5
    contrast_min: float = 0.8
    contrast_max: float = 1.15

    p_brightness: float = 0.5
    brightness_min: float = -0.07
    brightness_max: float = 0.07

    p_shade: float = 0.25
    shade_amp: float = 0.20

    p_noise: float = 0.5
    noise_sigma: float = 0.02

    p_blur: float = 0.2
    blur_ks: Tuple[int, ...] = (3, 5)

    p_frame_drop: float = 0.10
    frame_drop_max: int = 2


def parse_csv_groups(text: str) -> set[str]:
    """Parse a comma-separated list into a normalized lowercase token set."""
    if not text:
        return set()
    return {tok.strip().lower() for tok in text.split(",") if tok.strip()}


def build_aug_params(disable_groups: str = "") -> AugParams:
    """
    Build augmentation parameters after disabling named augmentation families.

    Supported group names:
      - spatial: hflip + affine
      - photometric: gamma + contrast + brightness + shade
      - acquisition: noise + blur
      - temporal: frame_drop

    Note:
      start-index jitter is handled separately in PairQueueDataset and is not part
      of AugParams. To disable the full temporal/sampling family in experiments,
      set `--jitter 0` together with `--aug_disable_groups temporal`.
    """
    groups = parse_csv_groups(disable_groups)
    valid = {"spatial", "photometric", "acquisition", "temporal"}
    unknown = sorted(groups - valid)
    if unknown:
        raise ValueError(f"Unknown augmentation group(s): {', '.join(unknown)}")

    aug = AugParams()
    if "spatial" in groups:
        aug.p_hflip = 0.0
        aug.p_affine = 0.0
    if "photometric" in groups:
        aug.p_gamma = 0.0
        aug.p_contrast = 0.0
        aug.p_brightness = 0.0
        aug.p_shade = 0.0
    if "acquisition" in groups:
        aug.p_noise = 0.0
        aug.p_blur = 0.0
    if "temporal" in groups:
        aug.p_frame_drop = 0.0
        aug.frame_drop_max = 0
    return aug


def _apply_box_blur_u8(frame_u8: np.ndarray, k: int) -> np.ndarray:
    """Fast box blur using integral image (uint8 -> float -> uint8)."""
    if k <= 1:
        return frame_u8
    pad = k // 2
    x = frame_u8.astype(np.float32)
    x = np.pad(x, ((pad, pad), (pad, pad)), mode="reflect")
    H2, W2 = x.shape
    ii = np.zeros((H2 + 1, W2 + 1), dtype=np.float32)
    ii[1:, 1:] = np.cumsum(np.cumsum(x, axis=0), axis=1)
    y = (ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]) / float(k * k)
    return np.clip(y, 0, 255).astype(np.uint8)


def apply_augment_clip_u8(clip_u8: np.ndarray, rng: np.random.Generator, p: AugParams) -> np.ndarray:
    """
    Apply stochastic augmentations to a clip [L,H,W] uint8.

    Returns a new uint8 clip. Augmentations are designed to be mild and preserve
    staging-relevant morphology.
    """
    out = clip_u8.copy()
    L, H, W = out.shape

    # frame drop: replace some frames with previous frame
    if rng.random() < p.p_frame_drop and p.frame_drop_max > 0:
        n_drop = int(rng.integers(1, p.frame_drop_max + 1))
        for _ in range(n_drop):
            t = int(rng.integers(1, L))
            out[t] = out[t - 1]

    # horizontal flip
    if rng.random() < p.p_hflip:
        out = out[:, :, ::-1].copy()

    # affine (same params for all frames)
    if rng.random() < p.p_affine and TVF is not None:
        angle = float(rng.uniform(-p.max_rotate_deg, p.max_rotate_deg))
        translate_px = (
            int(rng.uniform(-p.max_translate, p.max_translate) * W),
            int(rng.uniform(-p.max_translate, p.max_translate) * H),
        )
        scale = float(rng.uniform(p.scale_min, p.scale_max))
        tmp = []
        for t in range(L):
            img = torch.from_numpy(out[t]).unsqueeze(0).float() / 255.0
            img = TVF.affine(
                img,
                angle=angle,
                translate=list(translate_px),
                scale=scale,
                shear=[0.0, 0.0],
                interpolation=TVF.InterpolationMode.BILINEAR,
                fill=0.0,
            )
            tmp.append((img.clamp(0, 1) * 255.0 + 0.5).to(torch.uint8).squeeze(0).numpy())
        out = np.stack(tmp, axis=0)

    xf = out.astype(np.float32) / 255.0

    if rng.random() < p.p_gamma:
        gamma = float(rng.uniform(p.gamma_min, p.gamma_max))
        xf = np.clip(xf, 0.0, 1.0) ** gamma

    if rng.random() < p.p_contrast:
        c = float(rng.uniform(p.contrast_min, p.contrast_max))
        m = float(np.mean(xf))
        xf = (xf - m) * c + m

    if rng.random() < p.p_brightness:
        b = float(rng.uniform(p.brightness_min, p.brightness_max))
        xf = xf + b

    # shade: multiplicative low-frequency field
    if rng.random() < p.p_shade:
        grid = rng.normal(loc=0.0, scale=1.0, size=(8, 8)).astype(np.float32)
        grid = (grid - grid.mean()) / (grid.std() + 1e-6)
        shade = 1.0 + p.shade_amp * grid
        if Image is not None:
            im = Image.fromarray(((shade - shade.min()) / (shade.max() - shade.min() + 1e-6) * 255).astype(np.uint8))
            im = im.resize((W, H), resample=Image.BILINEAR)
            shade_u = np.asarray(im, dtype=np.float32) / 255.0
            shade_u = 0.75 + 0.5 * shade_u
        else:
            tile_h = int(np.ceil(H / 8))
            tile_w = int(np.ceil(W / 8))
            shade_u = np.kron(shade, np.ones((tile_h, tile_w), dtype=np.float32))[:H, :W]
            shade_u = np.clip(shade_u, 0.75, 1.25)
        xf = xf * shade_u[None, :, :]

    if rng.random() < p.p_noise:
        xf = xf + rng.normal(loc=0.0, scale=p.noise_sigma, size=xf.shape).astype(np.float32)

    xf = np.clip(xf, 0.0, 1.0)
    out = (xf * 255.0 + 0.5).astype(np.uint8)

    if rng.random() < p.p_blur:
        k = int(rng.choice(np.array(p.blur_ks)))
        for t in range(L):
            out[t] = _apply_box_blur_u8(out[t], k=k)

    return out


# ---------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------
class _LRUCache:
    """Very small LRU cache to avoid repeated memmap open overhead."""
    def __init__(self, max_items: int = 16):
        self.max_items = int(max_items)
        self._data: Dict[str, Any] = {}
        self._order: List[str] = []

    def get(self, key: str) -> Any | None:
        if key not in self._data:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._data[key]

    def put(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data[key] = value
            self._order.remove(key)
            self._order.append(key)
            return
        self._data[key] = value
        self._order.append(key)
        if len(self._order) > self.max_items:
            old = self._order.pop(0)
            self._data.pop(old, None)


class PairQueueDataset(Dataset):
    """
    Pair sampling dataset for temporal-difference consistency training.

    Each __getitem__ returns two clips from the same embryo:
      clip1 starting at s1 and clip2 starting at s2

    Returned fields:
      x1, x2 : uint8 tensors [L,1,H,W]
      offset1, offset2 : scalar targets in hours (T0_HPF + DT_H*s)
      start1, start2 : start indices (integers)

    Why pair sampling?
    - Absolute supervision: predict the correct offset time for each clip.
    - Difference supervision (optional): encourage p2 - p1 ≈ DT_H*(s2 - s1)
      within the same embryo, making predictions temporally consistent.

    Important: this dataset produces correlated samples within each embryo. Use
    embryo-level statistics for downstream inferential claims.
    """

    def __init__(
        self,
        proc_dir: Path,
        embryo_ids: Sequence[str],
        clip_len: int,
        augment: bool,
        aug: AugParams,
        seed: int,
        samples_per_embryo: int = 32,
        jitter: int = 2,
        cache_items: int = 16,
    ):
        self.proc_dir = Path(proc_dir)
        self.embryo_ids = filter_excluded(list(embryo_ids))
        if not self.embryo_ids:
            raise ValueError("No embryo ids after filtering.")
        self.clip_len = int(clip_len)
        self.augment = bool(augment)
        self.aug = aug
        self.samples_per_embryo = int(samples_per_embryo)
        self.jitter = int(jitter)
        self._cache = _LRUCache(max_items=cache_items)
        self.reseed(seed)
        self._queues: Dict[str, Tuple[int, List[int]]] = {}

    def reseed(self, seed: int) -> None:
        self.rng = np.random.default_rng(int(seed))

    def __len__(self) -> int:
        return max(1, len(self.embryo_ids) * self.samples_per_embryo)

    def _load(self, eid: str) -> np.ndarray:
        cached = self._cache.get(eid)
        if cached is not None:
            return cached
        arr = load_frames_memmap(self.proc_dir, eid)
        self._cache.put(eid, arr)
        return arr

    def _get_max_start_real(self, frames_T: int) -> int:
        return max(0, int(frames_T - self.clip_len))

    def _pop_start(self, eid: str, max_start_real: int) -> int:
        item = self._queues.get(eid, None)
        if item is None or item[0] != max_start_real or len(item[1]) == 0:
            q = list(range(0, max_start_real + 1))
            self.rng.shuffle(q)
            self._queues[eid] = (max_start_real, q)
        return int(self._queues[eid][1].pop())

    def _get_clip(self, frames: np.ndarray, start: int, max_start_real: int) -> np.ndarray:
        s = int(np.clip(start, 0, max_start_real))
        clip = np.array(frames[s:s + self.clip_len], dtype=np.uint8, copy=True)
        if clip.shape[0] != self.clip_len:
            pad = self.clip_len - clip.shape[0]
            clip = np.concatenate([clip, np.repeat(clip[-1:], pad, axis=0)], axis=0)
        return clip

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        eid = self.embryo_ids[idx % len(self.embryo_ids)]
        frames = self._load(eid)
        frames_T = int(frames.shape[0])
        max_start_real = self._get_max_start_real(frames_T)

        s1 = self._pop_start(eid, max_start_real)
        s2 = self._pop_start(eid, max_start_real)

        # jitter around sampled starts to reduce periodicity and improve coverage
        if self.jitter > 0 and max_start_real > 0:
            s1 = int(np.clip(s1 + int(self.rng.integers(-self.jitter, self.jitter + 1)), 0, max_start_real))
            s2 = int(np.clip(s2 + int(self.rng.integers(-self.jitter, self.jitter + 1)), 0, max_start_real))

        clip1 = self._get_clip(frames, s1, max_start_real)
        clip2 = self._get_clip(frames, s2, max_start_real)

        if self.augment:
            clip1 = apply_augment_clip_u8(clip1, self.rng, self.aug)
            clip2 = apply_augment_clip_u8(clip2, self.rng, self.aug)

        # Keep clips as uint8 inside DataLoader workers to reduce host-memory
        # pressure from prefetched batches. Normalization happens on-device.
        x1 = torch.from_numpy(np.ascontiguousarray(clip1)).unsqueeze(1)
        x2 = torch.from_numpy(np.ascontiguousarray(clip2)).unsqueeze(1)

        o1 = float(T0_HPF + DT_H * s1)
        o2 = float(T0_HPF + DT_H * s2)

        return {
            "eid": eid,
            "start1": int(s1),
            "start2": int(s2),
            "x1": x1,
            "x2": x2,
            "offset1": torch.tensor(o1, dtype=torch.float32),
            "offset2": torch.tensor(o2, dtype=torch.float32),
        }


class DeterministicValDataset(Dataset):
    """
    Deterministic clip-level evaluation dataset.

    For each embryo, enumerates all possible window starts:
      s = 0..(T - clip_len)

    Output sample:
      x : [L,1,H,W] uint8
      target : scalar offset time (hours)

    Note on statistics:
    - Samples from the same embryo are strongly correlated.
    - Clip-level MAE/RMSE are useful for tracking training but are not a valid
      unit for hypothesis testing; use embryo-level inference in analysis.
    """

    def __init__(self, proc_dir: Path, embryo_ids: Sequence[str], clip_len: int, cache_items: int = 16):
        self.proc_dir = Path(proc_dir)
        self.clip_len = int(clip_len)
        self.embryo_ids = filter_excluded(list(embryo_ids))
        self._cache = _LRUCache(max_items=cache_items)
        self.samples: List[Tuple[str, int]] = []
        for eid in self.embryo_ids:
            T = load_frames_T(self.proc_dir, eid)
            max_start_real = max(0, int(T - self.clip_len))
            for s in range(0, max_start_real + 1):
                self.samples.append((eid, s))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        eid, s = self.samples[idx]
        cached = self._cache.get(eid)
        if cached is None:
            cached = load_frames_memmap(self.proc_dir, eid)
            self._cache.put(eid, cached)
        frames = cached
        T = int(frames.shape[0])
        max_start_real = max(0, int(T - self.clip_len))
        s = int(np.clip(s, 0, max_start_real))

        clip = np.array(frames[s:s + self.clip_len], dtype=np.uint8, copy=True)
        if clip.shape[0] != self.clip_len:
            pad = self.clip_len - clip.shape[0]
            clip = np.concatenate([clip, np.repeat(clip[-1:], pad, axis=0)], axis=0)

        # Validation clips stay uint8 until they reach the device for the same
        # host-memory reason as training clips.
        x = torch.from_numpy(np.ascontiguousarray(clip)).unsqueeze(1)
        target = float(T0_HPF + DT_H * s)
        return {"eid": eid, "start": int(s), "x": x, "target": torch.tensor(target, dtype=torch.float32)}


# ---------------------------------------------------------------------
# Model components
# ---------------------------------------------------------------------
class SEBlock(nn.Module):
    """Squeeze-and-Excitation (channel attention) block."""
    def __init__(self, channels: int, reduction: int = 4, min_hidden: int = 8):
        super().__init__()
        hidden = max(channels // reduction, min_hidden)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Linear(channels, hidden)
        self.fc2 = nn.Linear(hidden, channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        w = self.pool(x).view(b, c)
        w = F.silu(self.fc1(w))
        w = torch.sigmoid(self.fc2(w)).view(b, c, 1, 1)
        return x * w


class DSConvSEBlock(nn.Module):
    """
    Depthwise-separable conv block with SE and GroupNorm.

    Intended as a lightweight CNN backbone appropriate for small batch sizes
    (GroupNorm is stable vs BatchNorm in DDP/small-batch regimes).
    """
    def __init__(self, c_in: int, c_out: int, stride: int = 1, expand_ratio: int = 2, se_reduction: int = 4):
        super().__init__()
        mid = c_in * expand_ratio
        self.use_res = (stride == 1 and c_in == c_out)
        self.pw1 = nn.Conv2d(c_in, mid, 1, bias=False)
        self.gn1 = nn.GroupNorm(gn_groups(mid), mid)
        self.dw = nn.Conv2d(mid, mid, 3, stride=stride, padding=1, groups=mid, bias=False)
        self.gn2 = nn.GroupNorm(gn_groups(mid), mid)
        self.pw2 = nn.Conv2d(mid, c_out, 1, bias=False)
        self.gn3 = nn.GroupNorm(gn_groups(c_out), c_out)
        self.se = SEBlock(c_out, reduction=se_reduction)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = F.silu(self.gn1(self.pw1(x)))
        y = F.silu(self.gn2(self.dw(y)))
        y = self.gn3(self.pw2(y))
        y = self.se(y)
        return (x + y) if self.use_res else y


class FrameEncoderLite(nn.Module):
    """
    Lightweight per-frame CNN encoder.

    Input:
      x: [B,1,H,W] float (0..1)

    Output:
      token: [B,D] float, where D=d_model

    Notes:
    - We intentionally compress each frame into a single token via global pooling.
      This makes the temporal module operate at the frame-token level.
    - Memory: optionally checkpoint CNN blocks during training.
    """
    def __init__(
        self,
        d_model: int,
        base: int = 24,
        expand_ratio: int = 2,
        se_reduction: int = 4,
        ckpt_cnn: bool = True,
        ckpt_segments: int = 2,
    ):
        super().__init__()
        self.ckpt_cnn = bool(ckpt_cnn)
        self.ckpt_segments = int(ckpt_segments)

        self.stem = nn.Sequential(
            nn.Conv2d(1, base, 3, stride=2, padding=1, bias=False),
            nn.GroupNorm(gn_groups(base), base),
            nn.SiLU(),
        )
        self.blocks = nn.Sequential(
            DSConvSEBlock(base, base, stride=2, expand_ratio=expand_ratio, se_reduction=se_reduction),
            DSConvSEBlock(base, base * 2, stride=2, expand_ratio=expand_ratio, se_reduction=se_reduction),
            DSConvSEBlock(base * 2, base * 2, stride=1, expand_ratio=expand_ratio, se_reduction=se_reduction),
            DSConvSEBlock(base * 2, base * 4, stride=2, expand_ratio=expand_ratio, se_reduction=se_reduction),
            DSConvSEBlock(base * 4, base * 4, stride=1, expand_ratio=expand_ratio, se_reduction=se_reduction),
            DSConvSEBlock(base * 4, base * 5, stride=2, expand_ratio=expand_ratio, se_reduction=se_reduction),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.proj = nn.Linear(base * 5, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        if self.ckpt_cnn and self.training:
            x = checkpoint_seq(self.blocks, self.ckpt_segments, x)
        else:
            x = self.blocks(x)
        x = self.pool(x).flatten(1)
        return self.proj(x)


class RoPE1D(nn.Module):
    """
    Rotary positional embedding for 1D sequences.

    Applied to Q,K in attention, enabling relative-position modeling.
    """
    def __init__(self, head_dim: int, base: float = 10000.0):
        super().__init__()
        if head_dim % 2 != 0:
            raise ValueError("RoPE requires even head_dim.")
        self.head_dim = int(head_dim)
        self.base = float(base)

    def build_cos_sin(self, seq_len: int, device: torch.device, dtype: torch.dtype) -> Tuple[torch.Tensor, torch.Tensor]:
        half = self.head_dim // 2
        inv_freq = 1.0 / (self.base ** (torch.arange(0, half, device=device).float() / half))
        pos = torch.arange(seq_len, device=device).float()
        ang = torch.outer(pos, inv_freq)  # [L, half]
        return ang.cos().to(dtype), ang.sin().to(dtype)

    @staticmethod
    def apply(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        x1 = x[..., ::2]
        x2 = x[..., 1::2]
        cos = cos[None, None, :, :]
        sin = sin[None, None, :, :]
        y1 = x1 * cos - x2 * sin
        y2 = x1 * sin + x2 * cos
        return torch.stack([y1, y2], dim=-1).flatten(-2)


class TemporalBlock(nn.Module):
    """
    Transformer block for temporal token sequences.

    Input:
      x: [B,L,D]

    Output:
      x': [B,L,D]

    Notes:
    - Uses RoPE for Q/K.
    - Uses PyTorch scaled_dot_product_attention when available (flash/SDPA).
    """
    def __init__(self, d_model: int, n_heads: int, mlp_ratio: float = 2.0, dropout: float = 0.1, attn_drop: float = 0.0):
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        head_dim = d_model // n_heads
        if head_dim % 2 != 0:
            raise ValueError("head_dim must be even for RoPE")
        self.n_heads = int(n_heads)
        self.head_dim = int(head_dim)

        self.norm1 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)
        self.drop = nn.Dropout(attn_drop)
        self.proj_drop = nn.Dropout(dropout)

        self.rope = RoPE1D(head_dim=head_dim)

        self.norm2 = nn.LayerNorm(d_model)
        hidden = int(d_model * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, L, D = x.shape
        y = self.norm1(x)
        q, k, v = self.qkv(y).chunk(3, dim=-1)

        q = q.view(B, L, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, L, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, L, self.n_heads, self.head_dim).transpose(1, 2)

        cos, sin = self.rope.build_cos_sin(L, device=x.device, dtype=x.dtype)
        q = self.rope.apply(q, cos, sin)
        k = self.rope.apply(k, cos, sin)

        if hasattr(F, "scaled_dot_product_attention"):
            a = F.scaled_dot_product_attention(
                q, k, v, attn_mask=None,
                dropout_p=self.drop.p if self.training else 0.0
            )
        else:
            scale = self.head_dim ** -0.5
            attn = (q @ k.transpose(-2, -1)) * scale
            attn = attn.softmax(dim=-1)
            attn = self.drop(attn)
            a = attn @ v

        a = a.transpose(1, 2).contiguous().view(B, L, D)
        a = self.proj_drop(self.out(a))

        x = x + a
        x = x + self.mlp(self.norm2(x))
        return x


class EmbryoTempoFormer(nn.Module):
    """
    Main model: per-frame CNN tokens + temporal aggregation + regression head.

    Input:
      x: [B, L, 1, H, W] float in [0,1]
         where L is clip_len (default 24).

    Output:
      pred: [B] float (hours, predicted offset time)

    Temporal modes:
      - identity : use only the first frame (single-frame baseline)
      - meanpool : average tokens across frames
      - transformer : prepend CLS and run temporal transformer blocks

    Memory controls:
      - frame_chunk : how many frames to encode per CNN call
      - ckpt_frame  : checkpoint whole frame encoder per chunk (OOM fix)
    """

    def __init__(
        self,
        d_model: int = 128,
        depth: int = 4,
        n_heads: int = 4,
        mlp_ratio: float = 2.0,
        dropout: float = 0.1,
        attn_drop: float = 0.0,
        temporal_drop_p: float = 0.0,
        temporal_mode: str = "transformer",  # transformer | meanpool | identity
        cnn_base: int = 24,
        cnn_expand: int = 2,
        cnn_se_reduction: int = 4,
        frame_chunk: int = 8,
        ckpt_frame: bool = False,
        ckpt_cnn: bool = True,
        ckpt_segments: int = 2,
    ):
        super().__init__()
        self.d_model = int(d_model)
        self.temporal_drop_p = float(temporal_drop_p)
        self.temporal_mode = str(temporal_mode)
        self.frame_chunk = int(frame_chunk)
        self.ckpt_frame = bool(ckpt_frame)

        self.frame_enc = FrameEncoderLite(
            d_model=self.d_model,
            base=int(cnn_base),
            expand_ratio=int(cnn_expand),
            se_reduction=int(cnn_se_reduction),
            ckpt_cnn=bool(ckpt_cnn),
            ckpt_segments=int(ckpt_segments),
        )

        self.cls_token = nn.Parameter(torch.zeros(1, 1, self.d_model))
        nn.init.trunc_normal_(self.cls_token, std=0.02)

        self.blocks = nn.ModuleList([
            TemporalBlock(
                d_model=self.d_model,
                n_heads=int(n_heads),
                mlp_ratio=float(mlp_ratio),
                dropout=float(dropout),
                attn_drop=float(attn_drop),
            )
            for _ in range(int(depth))
        ])
        self.norm = nn.LayerNorm(self.d_model)

        self.head = nn.Sequential(
            nn.Linear(self.d_model, self.d_model),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(self.d_model, 1),
        )

    def _encode_frames(self, x: torch.Tensor) -> torch.Tensor:
        """
        Encode frames in chunks to control memory.

        Args:
          x: [B,L,1,H,W]

        Returns:
          tokens: [B,L,D]
        """
        B, L, C, H, W = x.shape
        chunk = self.frame_chunk if self.frame_chunk > 0 else L
        toks = []
        for t0 in range(0, L, chunk):
            t1 = min(L, t0 + chunk)
            xs = x[:, t0:t1].reshape(B * (t1 - t0), C, H, W)
            if self.training and self.ckpt_frame:
                ts = checkpoint_call(self.frame_enc, xs)
            else:
                ts = self.frame_enc(xs)
            toks.append(ts.reshape(B, (t1 - t0), self.d_model))
        return torch.cat(toks, dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 5:
            raise ValueError(f"Expected [B,L,1,H,W], got {x.shape}")
        B = x.shape[0]

        mode = self.temporal_mode
        if mode not in ("transformer", "meanpool", "identity"):
            raise ValueError(f"Unknown temporal_mode={mode}")

        # identity baseline: use only first frame
        if mode == "identity":
            x = x[:, :1]

        tok = self._encode_frames(x)  # [B,Ltok,D]

        # temporal token drop (regularization)
        if self.training and self.temporal_drop_p > 0 and tok.shape[1] > 1:
            mask = (torch.rand(B, tok.shape[1], 1, device=tok.device) > self.temporal_drop_p).to(tok.dtype)
            tok = tok * mask / (1.0 - self.temporal_drop_p)

        if mode == "meanpool":
            feat = self.norm(tok.mean(dim=1))
            return self.head(feat).squeeze(-1)

        if mode == "identity":
            feat = self.norm(tok[:, 0])
            return self.head(feat).squeeze(-1)

        # transformer (default)
        cls = self.cls_token.expand(B, -1, -1)
        h = torch.cat([cls, tok], dim=1)
        for blk in self.blocks:
            h = blk(h)
        h = self.norm(h)
        return self.head(h[:, 0]).squeeze(-1)


# ---------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------
class EMA:
    """
    Exponential moving average of model weights.

    We store a shadow state_dict. During eval, we can temporarily swap model
    weights with EMA weights for smoother metrics.
    """
    def __init__(self, model: nn.Module, decay: float = 0.995):
        self.decay = float(decay)
        self.shadow: Dict[str, torch.Tensor] = {}
        self._init_from(model)

    def _raw(self, model: nn.Module) -> nn.Module:
        return model.module if hasattr(model, "module") else model

    @torch.no_grad()
    def _init_from(self, model: nn.Module) -> None:
        m = self._raw(model)
        self.shadow = {k: v.detach().clone() for k, v in m.state_dict().items()}

    @torch.no_grad()
    def update(self, model: nn.Module) -> None:
        m = self._raw(model)
        sd = m.state_dict()
        for k, v in sd.items():
            if k not in self.shadow:
                self.shadow[k] = v.detach().clone()
                continue
            if v.is_floating_point():
                self.shadow[k].mul_(self.decay).add_(v.detach(), alpha=(1.0 - self.decay))
            else:
                self.shadow[k] = v.detach().clone()

    @torch.no_grad()
    def copy_to(self, model: nn.Module) -> Dict[str, torch.Tensor]:
        m = self._raw(model)
        backup = {k: v.detach().clone() for k, v in m.state_dict().items()}
        m.load_state_dict(self.shadow, strict=True)
        return backup

    @torch.no_grad()
    def restore(self, model: nn.Module, backup: Dict[str, torch.Tensor]) -> None:
        m = self._raw(model)
        m.load_state_dict(backup, strict=True)


# ---------------------------------------------------------------------
# Training config and helpers
# ---------------------------------------------------------------------
@dataclass
class TrainConfig:
    """
    Training configuration (stored into checkpoint for reproducibility).

    Paths are strings to keep this dataclass JSON-friendly.
    """
    proc_dir: str
    split_json: str
    out_dir: str

    clip_len: int = DEFAULT_CLIP_LEN
    img_size: int = 384
    expect_t: int = EXPECT_T_DEFAULT

    batch_size: int = 64
    val_batch_size: int = 64
    num_workers: int = 8
    samples_per_embryo: int = 32
    jitter: int = 2
    aug_disable_groups: str = ""
    cache_items: int = 16
    val_cache_items: int = 16

    epochs: int = 200
    lr: float = 6e-4
    weight_decay: float = 0.01
    warmup_ratio: float = 0.01
    lr_min_ratio: float = 0.05
    max_grad_norm: float = 1.0
    grad_accum: int = 1

    model_dim: int = 128
    model_depth: int = 4
    model_heads: int = 4
    model_mlp_ratio: float = 2.0
    drop: float = 0.1
    attn_drop: float = 0.0
    temporal_drop_p: float = 0.0
    temporal_mode: str = "transformer"  # transformer|meanpool|identity

    cnn_base: int = 24
    cnn_expand: int = 2
    cnn_se_reduction: int = 4

    mem_profile: str = "balanced"

    lambda_abs: float = 1.0
    lambda_diff: float = 1.0
    cons_ramp_ratio: float = 0.2
    abs_loss_type: str = "l1"  # l1 or smoothl1

    amp: bool = True
    ema_decay: float = 0.0
    ema_start_ratio: float = 0.1
    ema_eval: bool = False

    seed: int = 42
    device: str = "auto"
    resume: str = ""
    init_ckpt: str = ""
    init_use_ema: bool = False
    freeze_frame_encoder: bool = False
    freeze_temporal: bool = False
    freeze_head: bool = False
    unfreeze_frame_proj: bool = False
    unfreeze_frame_tail_blocks: int = 0
    unfreeze_temporal_tail_blocks: int = 0
    save_every: int = 1
    patience: int = 0
    val_every: int = 1


def build_model(cfg: TrainConfig) -> nn.Module:
    """Construct EmbryoTempoFormer from a TrainConfig + memory profile."""
    mp = MEM_PROFILES.get(cfg.mem_profile, MEM_PROFILES["balanced"])
    return EmbryoTempoFormer(
        d_model=cfg.model_dim,
        depth=cfg.model_depth,
        n_heads=cfg.model_heads,
        mlp_ratio=cfg.model_mlp_ratio,
        dropout=cfg.drop,
        attn_drop=cfg.attn_drop,
        temporal_drop_p=cfg.temporal_drop_p,
        temporal_mode=cfg.temporal_mode,
        cnn_base=cfg.cnn_base,
        cnn_expand=cfg.cnn_expand,
        cnn_se_reduction=cfg.cnn_se_reduction,
        frame_chunk=int(mp["frame_chunk"]),
        ckpt_frame=bool(mp["ckpt_frame"]),
        ckpt_cnn=bool(mp["ckpt_cnn"]),
        ckpt_segments=int(mp["ckpt_segments"]),
    )


def _set_module_requires_grad(module: nn.Module, requires_grad: bool) -> None:
    for p in module.parameters():
        p.requires_grad = bool(requires_grad)


def _apply_finetune_policy(model: EmbryoTempoFormer, cfg: TrainConfig) -> Dict[str, int]:
    """
    Apply an optional fine-tuning freeze policy to the model in-place.

    Typical usage:
      - head-only: freeze frame encoder + temporal, keep head trainable
      - temporal-only adaptation: freeze frame encoder, keep temporal + head
      - frame-tail adaptation: freeze frame encoder, then unfreeze the last N
        DSConv blocks plus the projection layer
    """
    if cfg.freeze_frame_encoder:
        _set_module_requires_grad(model.frame_enc, False)
    if cfg.freeze_temporal:
        _set_module_requires_grad(model.blocks, False)
        _set_module_requires_grad(model.norm, False)
        model.cls_token.requires_grad = False
    if cfg.freeze_head:
        _set_module_requires_grad(model.head, False)

    if bool(cfg.unfreeze_frame_proj):
        _set_module_requires_grad(model.frame_enc.proj, True)

    tail_n = max(0, int(cfg.unfreeze_frame_tail_blocks))
    if tail_n > 0:
        # Re-enable the projection and the last N convolutional blocks.
        _set_module_requires_grad(model.frame_enc.proj, True)
        blocks = list(model.frame_enc.blocks.children())
        for blk in blocks[-min(tail_n, len(blocks)):]:
            _set_module_requires_grad(blk, True)

    temporal_tail_n = max(0, int(cfg.unfreeze_temporal_tail_blocks))
    if temporal_tail_n > 0:
        # Re-enable the final N temporal blocks plus cls/norm, which are part
        # of the minimal transformer readout path.
        model.cls_token.requires_grad = True
        _set_module_requires_grad(model.norm, True)
        blocks = list(model.blocks.children())
        for blk in blocks[-min(temporal_tail_n, len(blocks)):]:
            _set_module_requires_grad(blk, True)

    total = sum(int(p.numel()) for p in model.parameters())
    trainable = sum(int(p.numel()) for p in model.parameters() if p.requires_grad)
    return {"total_params": total, "trainable_params": trainable}


def build_loaders(cfg: TrainConfig, ddp: bool):
    """Build training/validation DataLoaders and samplers."""
    sp = jload(cfg.split_json)
    train_ids = filter_excluded(sp["train"])
    val_ids = filter_excluded(sp["val"])
    aug = build_aug_params(cfg.aug_disable_groups)

    ds_train = PairQueueDataset(
        Path(cfg.proc_dir), train_ids, cfg.clip_len,
        True, aug, cfg.seed,
        cfg.samples_per_embryo, cfg.jitter, cfg.cache_items
    )
    ds_val = DeterministicValDataset(Path(cfg.proc_dir), val_ids, cfg.clip_len, cache_items=cfg.val_cache_items)

    train_sampler = DistributedSampler(ds_train, shuffle=True) if ddp else None
    val_sampler = DistributedSampler(ds_val, shuffle=False) if ddp else None

    pin = torch.cuda.is_available()
    g = torch.Generator()
    g.manual_seed(cfg.seed)

    dl_train = DataLoader(
        ds_train,
        batch_size=cfg.batch_size,
        shuffle=(train_sampler is None),
        sampler=train_sampler,
        num_workers=cfg.num_workers,
        pin_memory=pin,
        drop_last=True,
        persistent_workers=(cfg.num_workers > 0),
        prefetch_factor=2 if cfg.num_workers > 0 else None,
        worker_init_fn=seed_worker,
        generator=g,
    )
    dl_val = DataLoader(
        ds_val,
        batch_size=cfg.val_batch_size,
        shuffle=False,
        sampler=val_sampler,
        num_workers=max(0, cfg.num_workers // 2),
        pin_memory=pin,
        drop_last=False,
        persistent_workers=(cfg.num_workers > 0),
        prefetch_factor=2 if cfg.num_workers > 0 else None,
        worker_init_fn=seed_worker,
        generator=g,
    )
    return dl_train, dl_val, train_sampler, val_sampler


def save_checkpoint(
    path: Path,
    model,
    optimizer,
    scheduler,
    scaler,
    ema,
    epoch: int,
    step: int,
    cfg: TrainConfig,
    best_mae: float
):
    """
    Save training state (model/optim/scheduler/scaler/ema + cfg/meta).

    `ema` is stored as a raw state_dict-like mapping (ema.shadow).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = model.module if isinstance(model, DDP) else model
    state = {
        "model": raw.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict() if scheduler else None,
        "scaler": scaler.state_dict() if scaler else None,
        "ema": (ema.shadow if ema else None),
        "epoch": int(epoch),
        "step": int(step),
        "best_mae": float(best_mae),
        "cfg": dataclasses.asdict(cfg),
        "meta": {"model_name": MODEL_NAME, "saved_at": now_str()},
    }
    torch.save(state, path)


def load_checkpoint(path: str, model, optimizer=None, scheduler=None, scaler=None, ema=None) -> Tuple[int, int, float]:
    """Load checkpoint into model and optional optimizer/scheduler/scaler/ema."""
    state = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(state["model"], strict=True)
    if optimizer is not None and state.get("optimizer") is not None:
        optimizer.load_state_dict(state["optimizer"])
    if scheduler is not None and state.get("scheduler") is not None:
        scheduler.load_state_dict(state["scheduler"])
    if scaler is not None and state.get("scaler") is not None:
        scaler.load_state_dict(state["scaler"])
    if ema is not None and state.get("ema") is not None:
        ema.shadow = state["ema"]
    return int(state.get("epoch", 0)), int(state.get("step", 0)), float(state.get("best_mae", float("inf")))


def linear_ramp(step: int, ramp_steps: int) -> float:
    """Linear ramp from 0->1 over ramp_steps (used for consistency loss warm-up)."""
    if ramp_steps <= 0:
        return 1.0
    return float(min(1.0, (step + 1) / float(ramp_steps)))


def _abs_loss(pred: torch.Tensor, target: torch.Tensor, kind: str) -> torch.Tensor:
    """Absolute-time regression loss (L1 or SmoothL1)."""
    if kind == "smoothl1":
        return F.smooth_l1_loss(pred, target)
    return F.l1_loss(pred, target)


def _move_clip_batch_to_device(x: torch.Tensor, device: torch.device, amp: bool) -> torch.Tensor:
    """
    Move a uint8 clip batch to `device` and normalize it to [0, 1].

    Keeping clips as uint8 inside DataLoader workers greatly reduces host-memory
    pressure from prefetched batches. We cast only after transfer.
    """
    target_dtype = torch.float16 if (amp and device.type == "cuda") else torch.float32
    x = x.to(device=device, dtype=target_dtype, non_blocking=True)
    return x.div_(255.0)


def train_one_epoch(
    model,
    dl_train,
    optimizer,
    scheduler,
    scaler,
    ema: Optional[EMA],
    device: torch.device,
    ddp: bool,
    cfg: TrainConfig,
    epoch: int,
    train_sampler,
    global_step: int,
    total_optim_steps: int,
) -> Tuple[Dict[str, float], int]:
    """
    One epoch of training.

    Objective:
      loss_abs  = average abs regression loss on two clips
      loss_cons = SmoothL1( (p2 - p1), DT_H*(s2 - s1) )
      loss      = lambda_abs * loss_abs + lambda_diff * ramp(step)*loss_cons

    Where:
      p1,p2 are predicted offsets (hours),
      s1,s2 are start indices,
      DT_H is sampling interval in hours.
    """
    model.train()
    if train_sampler is not None:
        train_sampler.set_epoch(epoch)

    # [loss, abs, cons, |err|, err^2, n_samples]
    sums = torch.zeros(6, device=device)
    ramp_steps = int(cfg.cons_ramp_ratio * total_optim_steps)

    autocast_ctx = torch.cuda.amp.autocast if device.type == "cuda" else None

    optimizer.zero_grad(set_to_none=True)
    accum = max(1, int(cfg.grad_accum))
    local_iter = 0

    for batch in dl_train:
        x1 = _move_clip_batch_to_device(batch["x1"], device, amp=cfg.amp)
        x2 = _move_clip_batch_to_device(batch["x2"], device, amp=cfg.amp)
        t1 = batch["offset1"].to(device, non_blocking=True)
        t2 = batch["offset2"].to(device, non_blocking=True)
        s1 = batch["start1"].to(device, non_blocking=True).float()
        s2 = batch["start2"].to(device, non_blocking=True).float()

        B = x1.shape[0]

        if autocast_ctx is not None:
            with autocast_ctx(enabled=(cfg.amp and device.type == "cuda")):
                p1 = model(x1)
                p2 = model(x2)

                loss_abs = 0.5 * (_abs_loss(p1, t1, cfg.abs_loss_type) + _abs_loss(p2, t2, cfg.abs_loss_type))
                loss_cons = F.smooth_l1_loss(p2 - p1, DT_H * (s2 - s1))
                ramp = linear_ramp(global_step, ramp_steps)
                loss = cfg.lambda_abs * loss_abs + cfg.lambda_diff * (ramp * loss_cons)

                loss_scaled = loss / float(accum)
        else:
            p1 = model(x1)
            p2 = model(x2)
            loss_abs = 0.5 * (_abs_loss(p1, t1, cfg.abs_loss_type) + _abs_loss(p2, t2, cfg.abs_loss_type))
            loss_cons = F.smooth_l1_loss(p2 - p1, DT_H * (s2 - s1))
            ramp = linear_ramp(global_step, ramp_steps)
            loss = cfg.lambda_abs * loss_abs + cfg.lambda_diff * (ramp * loss_cons)
            loss_scaled = loss / float(accum)

        if scaler is not None and scaler.is_enabled():
            scaler.scale(loss_scaled).backward()
        else:
            loss_scaled.backward()

        local_iter += 1
        do_step = (local_iter % accum == 0)

        if do_step:
            if scaler is not None and scaler.is_enabled():
                scaler.unscale_(optimizer)

            if cfg.max_grad_norm > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=cfg.max_grad_norm)

            stepped = True
            if scaler is not None and scaler.is_enabled():
                scale_before = scaler.get_scale()
                scaler.step(optimizer)
                scaler.update()
                stepped = (scaler.get_scale() >= scale_before)
            else:
                optimizer.step()

            optimizer.zero_grad(set_to_none=True)

            if stepped and scheduler is not None:
                scheduler.step()

            if ema is not None:
                if total_optim_steps > 0 and (global_step / float(total_optim_steps)) >= float(cfg.ema_start_ratio):
                    ema.update(model)

            global_step += 1

        with torch.no_grad():
            err1 = (p1 - t1)
            err2 = (p2 - t2)
            n = 2 * B
            sums[0] += loss.detach() * B
            sums[1] += loss_abs.detach() * B
            sums[2] += loss_cons.detach() * B
            sums[3] += err1.abs().sum() + err2.abs().sum()
            sums[4] += (err1**2).sum() + (err2**2).sum()
            sums[5] += float(n)

    if ddp:
        ddp_all_reduce_sum_(sums)

    n = float(sums[5].item())
    metrics = {
        "loss": float((sums[0] / (n / 2.0)).item()),
        "abs": float((sums[1] / (n / 2.0)).item()),
        "cons": float((sums[2] / (n / 2.0)).item()),
        "mae": float((sums[3] / n).item()),
        "rmse": float((sums[4] / n).sqrt().item()),
    }
    return metrics, global_step


@torch.no_grad()
def validate(model, dl_val, device: torch.device, ddp: bool, cfg: TrainConfig) -> Dict[str, float]:
    """
    Clip-level validation.

    Returns dict:
      loss, mae, rmse, r2

    Note: this is clip-level and correlated within embryo.
    """
    model.eval()
    sums = torch.zeros(4, device=device)    # [loss, |err|, err^2, n]
    r2_sums = torch.zeros(4, device=device) # sum_y, sum_y2, sum_err2, n

    autocast_ctx = torch.cuda.amp.autocast if device.type == "cuda" else None

    for batch in dl_val:
        x = _move_clip_batch_to_device(batch["x"], device, amp=cfg.amp)
        y = batch["target"].to(device, non_blocking=True)

        if autocast_ctx is not None:
            with autocast_ctx(enabled=(cfg.amp and device.type == "cuda")):
                p = model(x)
                loss = F.l1_loss(p, y)
        else:
            p = model(x)
            loss = F.l1_loss(p, y)

        err = p - y
        B = x.shape[0]
        sums[0] += loss * B
        sums[1] += err.abs().sum()
        sums[2] += (err**2).sum()
        sums[3] += float(B)

        r2_sums[0] += y.sum()
        r2_sums[1] += (y**2).sum()
        r2_sums[2] += (err**2).sum()
        r2_sums[3] += float(B)

    if ddp:
        ddp_all_reduce_sum_(sums)
        ddp_all_reduce_sum_(r2_sums)

    n = float(sums[3].item())
    metrics = {
        "loss": float((sums[0] / max(1.0, n)).item()),
        "mae": float((sums[1] / max(1.0, n)).item()),
        "rmse": float((sums[2] / max(1.0, n)).sqrt().item()),
        "r2": ddp_r2_from_stats(r2_sums[0], r2_sums[1], r2_sums[2], r2_sums[3]),
    }
    return metrics


def _trainconfig_from_ckpt_cfg(ck_cfg: Dict[str, Any], overrides: Dict[str, Any]) -> TrainConfig:
    """Rebuild TrainConfig from checkpoint cfg dict, applying overrides."""
    fields = set(TrainConfig.__dataclass_fields__.keys())
    base = {k: ck_cfg[k] for k in ck_cfg.keys() if k in fields}
    base.update(overrides)
    return TrainConfig(**base)


# ---------------------------------------------------------------------
# Commands: train / eval / infer / preprocess / make_split
# ---------------------------------------------------------------------
def cmd_train(args):
    if args.resume and args.init_ckpt:
        raise ValueError("Use either --resume or --init_ckpt, not both.")

    cfg = TrainConfig(
        proc_dir=args.proc_dir, split_json=args.split_json, out_dir=args.out_dir,
        clip_len=args.clip_len, img_size=args.img_size, expect_t=args.expect_t,
        batch_size=args.batch_size, val_batch_size=args.val_batch_size, num_workers=args.num_workers,
        samples_per_embryo=args.samples_per_embryo, jitter=args.jitter,
        aug_disable_groups=args.aug_disable_groups, cache_items=args.cache_items, val_cache_items=args.val_cache_items,
        epochs=args.epochs, lr=args.lr, weight_decay=args.weight_decay, warmup_ratio=args.warmup_ratio,
        lr_min_ratio=args.lr_min_ratio, max_grad_norm=args.max_grad_norm, grad_accum=args.grad_accum,
        model_dim=args.model_dim, model_depth=args.model_depth, model_heads=args.model_heads,
        model_mlp_ratio=args.model_mlp_ratio, drop=args.drop, attn_drop=args.attn_drop, temporal_drop_p=args.temporal_drop_p,
        temporal_mode=args.temporal_mode,
        cnn_base=args.cnn_base, cnn_expand=args.cnn_expand, cnn_se_reduction=args.cnn_se_reduction,
        mem_profile=args.mem_profile,
        lambda_abs=args.lambda_abs, lambda_diff=args.lambda_diff, cons_ramp_ratio=args.cons_ramp_ratio, abs_loss_type=args.abs_loss_type,
        amp=args.amp, ema_decay=args.ema_decay, ema_start_ratio=args.ema_start_ratio, ema_eval=args.ema_eval,
        seed=args.seed, device=args.device, resume=args.resume, init_ckpt=args.init_ckpt, init_use_ema=args.init_use_ema,
        freeze_frame_encoder=args.freeze_frame_encoder, freeze_temporal=args.freeze_temporal, freeze_head=args.freeze_head,
        unfreeze_frame_proj=args.unfreeze_frame_proj,
        unfreeze_frame_tail_blocks=args.unfreeze_frame_tail_blocks,
        unfreeze_temporal_tail_blocks=args.unfreeze_temporal_tail_blocks,
        save_every=args.save_every, patience=args.patience, val_every=args.val_every
    )

    device, ddp = ddp_init()

    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass

    seed_all(cfg.seed + ddp_rank())

    model = build_model(cfg).to(device)

    if cfg.init_ckpt:
        init_state = torch.load(cfg.init_ckpt, map_location="cpu", weights_only=False)
        _load_ckpt_weights_into_model(model, init_state, use_ema=bool(cfg.init_use_ema))
        if ddp_is_main():
            src = "ema" if cfg.init_use_ema and init_state.get("ema") is not None else "model"
            print(f"[init_ckpt] loaded {src} weights from {cfg.init_ckpt}")

    finetune_stats = _apply_finetune_policy(model, cfg)
    if finetune_stats["trainable_params"] <= 0:
        raise ValueError("No trainable parameters remain after applying the freeze policy.")
    if ddp_is_main():
        print(
            f"[trainable] {finetune_stats['trainable_params']:,} / "
            f"{finetune_stats['total_params']:,} parameters"
        )

    if ddp:
        model = DDP(
            model,
            device_ids=[device.index] if device.type == "cuda" else None,
            find_unused_parameters=(cfg.temporal_mode != "transformer")
        )

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=cfg.lr, weight_decay=cfg.weight_decay)
    dl_train, dl_val, train_sampler, _ = build_loaders(cfg, ddp=ddp)

    steps_per_epoch = max(1, math.ceil(len(dl_train) / max(1, int(cfg.grad_accum))))
    total_optim_steps = max(1, cfg.epochs * steps_per_epoch)
    warmup_steps = min(max(1, int(cfg.warmup_ratio * total_optim_steps)), total_optim_steps)

    def lr_lambda(step: int):
        if step < warmup_steps:
            return (step + 1) / float(warmup_steps)
        if total_optim_steps == warmup_steps:
            return cfg.lr_min_ratio
        t = (step - warmup_steps) / max(1, total_optim_steps - warmup_steps)
        cosine = 0.5 * (1 + math.cos(math.pi * t))
        return cfg.lr_min_ratio + (1 - cfg.lr_min_ratio) * cosine

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
    scaler = torch.cuda.amp.GradScaler(enabled=(cfg.amp and device.type == "cuda"))

    ema = None
    if cfg.ema_decay and cfg.ema_decay > 0:
        raw = model.module if isinstance(model, DDP) else model
        ema = EMA(raw, decay=cfg.ema_decay)

    out_dir = Path(cfg.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = out_dir / "ckpt"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    hist_path = out_dir / "history.csv"

    if ddp_is_main():
        dump_run_config(out_dir, cfg)

    start_epoch = 0
    global_step = 0
    best_mae = float("inf")
    epochs_without_improve = 0

    if cfg.resume:
        raw = model.module if isinstance(model, DDP) else model
        se, ss, bm = load_checkpoint(cfg.resume, raw, optimizer, scheduler, scaler, ema)
        start_epoch = se + 1
        global_step = ss
        best_mae = bm
        if ddp_is_main():
            print(f"[resume] epoch={start_epoch} global_step={global_step} best_mae={best_mae:.6f}")

    # initialize history.csv
    if ddp_is_main() and not hist_path.exists():
        with open(hist_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "epoch", "step",
                "train_loss", "train_mae", "train_rmse", "train_abs", "train_cons",
                "val_loss", "val_mae", "val_rmse", "val_r2",
                "lr", "secs", "mem_profile", "gpu_mem_gb_rank0"
            ])

    for epoch in range(start_epoch, cfg.epochs):
        t0 = time.time()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats()
        should_stop = False

        train_m, global_step = train_one_epoch(
            model, dl_train, optimizer, scheduler, scaler, ema,
            device, ddp, cfg, epoch, train_sampler, global_step,
            total_optim_steps=total_optim_steps,
        )

        run_val = ((epoch + 1) % max(1, int(cfg.val_every)) == 0) or (epoch == cfg.epochs - 1)
        val_m = {"loss": float("nan"), "mae": float("nan"), "rmse": float("nan"), "r2": float("nan")}
        if run_val:
            # EMA eval swap
            backup = None
            if ema is not None and cfg.ema_eval:
                raw = model.module if isinstance(model, DDP) else model
                backup = ema.copy_to(raw)

            val_m = validate(model, dl_val, device, ddp, cfg)

            if backup is not None and ema is not None:
                raw = model.module if isinstance(model, DDP) else model
                ema.restore(raw, backup)

        secs = time.time() - t0
        lr_cur = scheduler.get_last_lr()[0]
        mem_gb = float(torch.cuda.max_memory_reserved() / (1024**3)) if device.type == "cuda" else float("nan")

        if ddp_is_main():
            with open(hist_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    epoch, global_step,
                    train_m["loss"], train_m["mae"], train_m["rmse"], train_m["abs"], train_m["cons"],
                    val_m["loss"], val_m["mae"], val_m["rmse"], val_m["r2"],
                    lr_cur, secs, cfg.mem_profile, mem_gb
                ])

            if (epoch + 1) % cfg.save_every == 0:
                save_checkpoint(ckpt_dir / f"epoch{epoch+1}.pt", model, optimizer, scheduler, scaler, ema, epoch, global_step, cfg, best_mae)

            if run_val and val_m["mae"] + 1e-9 < best_mae:
                best_mae = float(val_m["mae"])
                epochs_without_improve = 0
                save_checkpoint(out_dir / "best.pt", model, optimizer, scheduler, scaler, ema, epoch, global_step, cfg, best_mae)
            elif run_val:
                epochs_without_improve += 1

            print(
                f"[epoch {epoch}] train_mae={train_m['mae']:.3f} "
                f"val_mae={val_m['mae']:.3f} lr={lr_cur:.2e} mem={mem_gb:.1f}GB "
                f"profile={cfg.mem_profile} val_run={int(run_val)}"
            )

            if run_val and cfg.patience > 0 and epochs_without_improve >= int(cfg.patience):
                print(
                    f"[early-stop] no val_mae improvement for {epochs_without_improve} epoch(s); "
                    f"stopping at epoch {epoch} with best_mae={best_mae:.6f}"
                )
                should_stop = True

        if ddp:
            stop_flag = torch.tensor([1 if should_stop else 0], device=device, dtype=torch.int32)
            dist.all_reduce(stop_flag, op=dist.ReduceOp.MAX)
            should_stop = bool(int(stop_flag.item()) > 0)

        if should_stop:
            break

    if ddp_is_main():
        last_epoch_done = epoch if "epoch" in locals() else max(0, start_epoch - 1)
        save_checkpoint(out_dir / "last.pt", model, optimizer, scheduler, scaler, ema, last_epoch_done, global_step, cfg, best_mae)

    if ddp:
        dist.destroy_process_group()


def _load_ckpt_weights_into_model(model: nn.Module, ck: Dict[str, Any], use_ema: bool) -> None:
    """
    Load weights from checkpoint into model.

    ck["model"] always exists.
    ck["ema"] may exist if EMA was enabled; it is stored as a state_dict mapping.
    """
    if use_ema and ck.get("ema") is not None:
        model.load_state_dict(ck["ema"], strict=True)
    else:
        model.load_state_dict(ck["model"], strict=True)


def cmd_eval(args):
    """
    Evaluate clip-level metrics on the validation split.

    This uses DeterministicValDataset (all starts per embryo), so metrics are
    clip-level and correlated. Use embryo-level analysis for statistical claims.
    """
    device = ensure_device(args.device)

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    ck_cfg = ck.get("cfg", {}) if isinstance(ck, dict) else {}

    overrides = dict(
        proc_dir=args.proc_dir,
        split_json=args.split_json,
        out_dir=_default_out_dir_for_nontrain(),
        clip_len=args.clip_len,
        img_size=args.img_size,
        expect_t=args.expect_t,
        batch_size=args.batch_size,
        val_batch_size=args.batch_size,
        num_workers=args.num_workers,
        amp=args.amp,
        device=args.device,
        mem_profile=args.mem_profile,
    )
    cfg = _trainconfig_from_ckpt_cfg(ck_cfg, overrides)

    model = build_model(cfg)
    _load_ckpt_weights_into_model(model, ck, use_ema=bool(args.use_ema))
    model.to(device)

    sp = jload(cfg.split_json)
    val_ids = filter_excluded(sp["val"])
    ds_val = DeterministicValDataset(Path(cfg.proc_dir), val_ids, clip_len=cfg.clip_len)
    dl_val = DataLoader(ds_val, batch_size=cfg.val_batch_size, shuffle=False, num_workers=cfg.num_workers, pin_memory=True)

    metrics = validate(model, dl_val, device, ddp=False, cfg=cfg)
    print(metrics)


def trimmed_mean(x: Sequence[float], trim: float = 0.2) -> float:
    """
    Robust trimmed mean.

    trim=0.0 means ordinary mean.
    trim=0.2 means drop 20% lowest and 20% highest values.
    """
    xs = np.sort(np.asarray(list(x), dtype=np.float64))
    if xs.size == 0:
        return float("nan")
    k = int(trim * xs.size)
    if k <= 0:
        return float(xs.mean())
    if 2 * k >= xs.size:
        return float(xs.mean())
    return float(xs[k:-k].mean())


@torch.no_grad()
def infer_full_embryo_from_proc(
    model: nn.Module,
    frames_u8: np.ndarray,
    device: torch.device,
    clip_len: int,
    stride: int = 8,
    trim: float = 0.2,
    amp: bool = True,
) -> Dict[str, Any]:
    """
    Embryo-level inference on a full sequence.

    For each window start s:
      - predict offset(s) in hours
      - compute t0_hat(s) = offset(s) - DT_H*s

    Aggregate:
      t0_final = trimmed_mean(t0_hat(s), trim)

    Also returns simple metrics against a nominal time axis:
      y_true(t) = T0_HPF + DT_H*t
      y_pred(t) = t0_final + DT_H*t
    These are *not* external-temperature ground truth metrics; they mainly serve
    as internal consistency checks.

    Returns JSON-serializable dict.
    """
    model.eval()
    T = int(frames_u8.shape[0])
    starts = list(range(0, max(1, T - clip_len + 1), int(stride)))
    t0_hats = []

    autocast_ctx = torch.cuda.amp.autocast if device.type == "cuda" else None

    for s in starts:
        clip = np.asarray(frames_u8[s:s + clip_len], dtype=np.uint8)
        if clip.shape[0] != clip_len:
            pad = clip_len - clip.shape[0]
            clip = np.concatenate([clip, np.repeat(clip[-1:], pad, axis=0)], axis=0)

        x = torch.from_numpy(np.ascontiguousarray(clip)).unsqueeze(0).unsqueeze(2).float().to(device) / 255.0
        if amp and device.type == "cuda":
            x = x.half()

        if autocast_ctx is not None:
            with autocast_ctx(enabled=(amp and device.type == "cuda")):
                offset = float(model(x).item())
        else:
            offset = float(model(x).item())

        t0_hats.append(offset - DT_H * s)

    t0_final = trimmed_mean(t0_hats, trim=trim)

    y_pred = t0_final + DT_H * np.arange(T, dtype=np.float64)
    y_true = T0_HPF + DT_H * np.arange(T, dtype=np.float64)
    metrics = mae_rmse_np(y_true, y_pred)

    return {"t0_final": float(t0_final), "starts": starts, "t0_hats": t0_hats, "metrics": metrics}


def cmd_infer(args):
    """
    Inference for a single embryo stack.

    - input_path can be `.npy` (preferred) or `.tif/.tiff` (will preprocess on the fly)
    - output is a JSON file containing embryo-level inference results

    Note: This command reconstructs a TrainConfig from the checkpoint cfg to
    build the correct model architecture (dim/depth/temporal_mode/etc.).
    """
    device = ensure_device(args.device)

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    ck_cfg = ck.get("cfg", {}) if isinstance(ck, dict) else {}

    inferred_out_dir = str(Path(args.out_json).resolve().parent)

    overrides = dict(
        proc_dir=args.proc_dir or ck_cfg.get("proc_dir", ""),
        split_json=args.split_json or ck_cfg.get("split_json", ""),
        out_dir=inferred_out_dir,
        clip_len=args.clip_len,
        img_size=args.img_size,
        expect_t=args.expect_t,
        batch_size=args.batch_size,
        val_batch_size=args.batch_size,
        num_workers=args.num_workers,
        amp=args.amp,
        device=args.device,
        mem_profile=args.mem_profile,
    )
    cfg = _trainconfig_from_ckpt_cfg(ck_cfg, overrides)

    model = build_model(cfg)
    _load_ckpt_weights_into_model(model, ck, use_ema=bool(args.use_ema))
    model.to(device)

    in_path = Path(args.input_path)

    # Accept either processed npy or raw tiff.
    if in_path.suffix.lower() in [".tif", ".tiff"]:
        raw = read_tiff_stack(in_path)
        proc, meta = preprocess_stack(raw, expect_t=cfg.expect_t, img_size=cfg.img_size)
        frames_u8 = proc
        info = {"source": "tiff", "meta": meta}
    else:
        frames_u8 = np.load(in_path, mmap_mode=None)
        info = {"source": "npy"}

    out = infer_full_embryo_from_proc(
        model,
        frames_u8=frames_u8,
        device=device,
        clip_len=cfg.clip_len,
        stride=args.stride,
        trim=args.trim,
        amp=cfg.amp,
    )
    out.update(info)

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    jdump(out, out_path)
    print(f"Saved: {out_path}")


def cmd_preprocess(args):
    """
    Preprocess a directory of TIFF/OME-TIFF files into processed `.npy`.

    Notes:
    - This function does NOT recurse into subdirectories. Point --in_dir at the
      directory containing the tif files.
    - It writes a single preprocess_meta.json summarizing per-file preprocessing.
    """
    in_dir = Path(args.in_dir)
    proc_dir = Path(args.proc_dir)
    proc_dir.mkdir(parents=True, exist_ok=True)

    tiffs = sorted([p for p in in_dir.glob("*.tif*")])
    if not tiffs:
        raise FileNotFoundError(f"No tiffs in {in_dir}")

    meta_all = {}
    for p in tiffs:
        eid = p.stem
        if is_excluded(eid):
            continue
        raw = read_tiff_stack(p, max_pages=args.max_pages if args.max_pages > 0 else None)
        proc, meta = preprocess_stack(raw, expect_t=args.expect_t, img_size=args.img_size, p_lo=args.p_lo, p_hi=args.p_hi)
        save_proc_npy(proc_dir, eid, proc)
        meta_all[eid] = meta
        if args.limit > 0 and len(meta_all) >= args.limit:
            break

    # IMPORTANT: args contains `func` (callable) -> not JSON serializable.
    jdump({"meta": meta_all, "args": _jsonable_args(args)}, proc_dir / "preprocess_meta.json")
    print(f"[done] saved {len(meta_all)} embryos to {proc_dir}")


def cmd_make_split(args):
    """
    Create a split JSON by scanning proc_dir for `*.npy` files.

    Output JSON has keys: train/val/test.
    """
    proc_dir = Path(args.proc_dir)
    npys = sorted([p for p in proc_dir.glob("*.npy")])
    ids = [p.stem for p in npys if not is_excluded(p.stem)]
    if not ids:
        raise ValueError("No embryos found for split.")

    rng = np.random.default_rng(args.seed)
    rng.shuffle(ids)

    n = len(ids)
    n_val = int(round(n * args.val_ratio))
    n_test = int(round(n * args.test_ratio))
    n_train = max(1, n - n_val - n_test)

    train = ids[:n_train]
    val = ids[n_train:n_train + n_val]
    test = ids[n_train + n_val:]

    sp = {"train": train, "val": val, "test": test}
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    jdump(sp, out)
    print(f"[split] n={n} train={len(train)} val={len(val)} test={len(test)} -> {out}")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(prog=MODEL_NAME)
    sub = p.add_subparsers(dest="cmd", required=True)

    # preprocess
    sp = sub.add_parser("preprocess", help="Preprocess TIFF/OME-TIFF stacks into fixed-shape uint8 .npy")
    sp.add_argument("--in_dir", required=True, help="Directory containing *.tif* files (non-recursive).")
    sp.add_argument("--proc_dir", required=True, help="Output directory for processed *.npy and preprocess_meta.json.")
    sp.add_argument("--expect_t", type=int, default=EXPECT_T_DEFAULT, help="Target number of frames (pad/trim).")
    sp.add_argument("--img_size", type=int, default=384, help="Resize output frames to img_size x img_size.")
    sp.add_argument("--p_lo", type=float, default=1.0, help="Lower percentile for intensity clipping.")
    sp.add_argument("--p_hi", type=float, default=99.0, help="Upper percentile for intensity clipping.")
    sp.add_argument("--max_pages", type=int, default=0, help="Cap TIFF pages read (0=all).")
    sp.add_argument("--limit", type=int, default=0, help="Limit number of embryos processed (0=no limit).")
    sp.set_defaults(func=cmd_preprocess)

    # make_split
    sp = sub.add_parser("make_split", help="Create train/val/test split JSON by scanning proc_dir/*.npy")
    sp.add_argument("--proc_dir", required=True)
    sp.add_argument("--out_json", required=True)
    sp.add_argument("--val_ratio", type=float, default=0.15)
    sp.add_argument("--test_ratio", type=float, default=0.15)
    sp.add_argument("--seed", type=int, default=42)
    sp.set_defaults(func=cmd_make_split)

    # train
    sp = sub.add_parser("train", help="Train EmbryoTempoFormer with pair sampling and optional consistency loss.")
    sp.add_argument("--proc_dir", required=True)
    sp.add_argument("--split_json", required=True)
    sp.add_argument("--out_dir", required=True)

    sp.add_argument("--epochs", type=int, default=200)
    sp.add_argument("--batch_size", type=int, default=64)
    sp.add_argument("--val_batch_size", type=int, default=64)
    sp.add_argument("--num_workers", type=int, default=8)
    sp.add_argument("--samples_per_embryo", type=int, default=32)
    sp.add_argument("--jitter", type=int, default=2)
    sp.add_argument(
        "--aug_disable_groups",
        type=str,
        default="",
        help="Comma-separated augmentation families to disable: spatial, photometric, acquisition, temporal",
    )
    sp.add_argument("--cache_items", type=int, default=16)
    sp.add_argument("--val_cache_items", type=int, default=16)

    sp.add_argument("--lr", type=float, default=6e-4)
    sp.add_argument("--weight_decay", type=float, default=0.01)
    sp.add_argument("--warmup_ratio", type=float, default=0.01)
    sp.add_argument("--lr_min_ratio", type=float, default=0.05)
    sp.add_argument("--max_grad_norm", type=float, default=1.0)
    sp.add_argument("--grad_accum", type=int, default=1)

    sp.add_argument("--clip_len", type=int, default=DEFAULT_CLIP_LEN)
    sp.add_argument("--img_size", type=int, default=384)
    sp.add_argument("--expect_t", type=int, default=EXPECT_T_DEFAULT)

    sp.add_argument("--model_dim", type=int, default=128)
    sp.add_argument("--model_depth", type=int, default=4)
    sp.add_argument("--model_heads", type=int, default=4)
    sp.add_argument("--model_mlp_ratio", type=float, default=2.0)
    sp.add_argument("--drop", type=float, default=0.1)
    sp.add_argument("--attn_drop", type=float, default=0.0)
    sp.add_argument("--temporal_drop_p", type=float, default=0.0)
    sp.add_argument("--temporal_mode", type=str, default="transformer", choices=["transformer", "meanpool", "identity"])

    sp.add_argument("--cnn_base", type=int, default=24)
    sp.add_argument("--cnn_expand", type=int, default=2)
    sp.add_argument("--cnn_se_reduction", type=int, default=4)

    sp.add_argument("--mem_profile", type=str, default="balanced", choices=list(MEM_PROFILES.keys()))

    sp.add_argument("--lambda_abs", type=float, default=1.0)
    sp.add_argument("--lambda_diff", type=float, default=1.0)
    sp.add_argument("--cons_ramp_ratio", type=float, default=0.2)
    sp.add_argument("--abs_loss_type", type=str, default="l1", choices=["l1", "smoothl1"])

    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--device", type=str, default="auto")
    sp.add_argument("--resume", type=str, default="")
    sp.add_argument("--init_ckpt", type=str, default="", help="Initialize model weights from a checkpoint but start a fresh optimizer/scheduler.")
    sp.add_argument("--init_use_ema", action=argparse.BooleanOptionalAction, default=False, help="When used with --init_ckpt, load EMA weights if present.")
    sp.add_argument("--freeze_frame_encoder", action=argparse.BooleanOptionalAction, default=False)
    sp.add_argument("--freeze_temporal", action=argparse.BooleanOptionalAction, default=False)
    sp.add_argument("--freeze_head", action=argparse.BooleanOptionalAction, default=False)
    sp.add_argument("--unfreeze_frame_proj", action=argparse.BooleanOptionalAction, default=False, help="Re-enable only the frame projection layer after freezing the frame encoder.")
    sp.add_argument("--unfreeze_frame_tail_blocks", type=int, default=0, help="After freezing the frame encoder, re-enable the last N DSConv blocks plus the projection layer.")
    sp.add_argument("--unfreeze_temporal_tail_blocks", type=int, default=0, help="After freezing temporal modules, re-enable the last N temporal blocks plus cls/norm.")
    sp.add_argument("--save_every", type=int, default=1)
    sp.add_argument("--patience", type=int, default=0)
    sp.add_argument("--val_every", type=int, default=1, help="Run full validation every N epochs (always runs on the final epoch).")

    sp.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    sp.add_argument("--ema_decay", type=float, default=0.0)
    sp.add_argument("--ema_start_ratio", type=float, default=0.1)
    sp.add_argument("--ema_eval", action=argparse.BooleanOptionalAction, default=False)
    sp.set_defaults(func=cmd_train)

    # eval
    sp = sub.add_parser("eval", help="Clip-level evaluation on validation split.")
    sp.add_argument("--proc_dir", required=True)
    sp.add_argument("--split_json", required=True)
    sp.add_argument("--ckpt", required=True)
    sp.add_argument("--clip_len", type=int, default=DEFAULT_CLIP_LEN)
    sp.add_argument("--img_size", type=int, default=384)
    sp.add_argument("--expect_t", type=int, default=EXPECT_T_DEFAULT)
    sp.add_argument("--batch_size", type=int, default=64)
    sp.add_argument("--num_workers", type=int, default=4)
    sp.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    sp.add_argument("--device", type=str, default="auto")
    sp.add_argument("--mem_profile", type=str, default="balanced", choices=list(MEM_PROFILES.keys()))
    sp.add_argument("--use_ema", action=argparse.BooleanOptionalAction, default=False, help="Load EMA weights if present in ckpt.")
    sp.set_defaults(func=cmd_eval)

    # infer
    sp = sub.add_parser("infer", help="Embryo-level inference: sliding windows + t0_hat aggregation.")
    sp.add_argument("--ckpt", required=True)
    sp.add_argument("--input_path", required=True)
    sp.add_argument("--out_json", required=True)
    sp.add_argument("--proc_dir", type=str, default="")
    sp.add_argument("--split_json", type=str, default="")
    sp.add_argument("--clip_len", type=int, default=DEFAULT_CLIP_LEN)
    sp.add_argument("--img_size", type=int, default=384)
    sp.add_argument("--expect_t", type=int, default=EXPECT_T_DEFAULT)
    sp.add_argument("--batch_size", type=int, default=1)
    sp.add_argument("--num_workers", type=int, default=0)
    sp.add_argument("--stride", type=int, default=8)
    sp.add_argument("--trim", type=float, default=0.2)
    sp.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    sp.add_argument("--device", type=str, default="auto")
    sp.add_argument("--mem_profile", type=str, default="balanced", choices=list(MEM_PROFILES.keys()))
    sp.add_argument("--use_ema", action=argparse.BooleanOptionalAction, default=False, help="Load EMA weights if present in ckpt.")
    sp.set_defaults(func=cmd_infer)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
