from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None


def jdump(obj: Any, path: Path) -> None:
    """Write UTF-8 JSON, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def percentile_clip_to_u8(arr: np.ndarray, p_lo: float = 1.0, p_hi: float = 99.0) -> Tuple[np.ndarray, Dict[str, float]]:
    """Percentile clip and normalize to uint8 in [0, 255]."""
    lo = float(np.percentile(arr, p_lo))
    hi = float(np.percentile(arr, p_hi))
    if hi <= lo + 1e-12:
        hi = lo + 1.0
    x = np.clip(arr.astype(np.float32), lo, hi)
    x = (x - lo) / (hi - lo + 1e-12)
    x = np.clip(x, 0.0, 1.0)
    u8 = (x * 255.0 + 0.5).astype(np.uint8)
    return u8, {"p_lo": lo, "p_hi": hi}


def resize_stack_u8(frames_u8: np.ndarray, img_size: int) -> np.ndarray:
    """Resize uint8 [T,H,W] stack to [T,img_size,img_size] using bilinear resize."""
    if frames_u8.ndim != 3 or frames_u8.dtype != np.uint8:
        raise ValueError("Expected uint8 [T,H,W]")
    t, h, w = frames_u8.shape
    if h == img_size and w == img_size:
        return frames_u8
    if Image is None:
        raise RuntimeError("PIL not installed for resizing")
    out = []
    for i in range(t):
        im = Image.fromarray(frames_u8[i])
        im = im.resize((img_size, img_size), resample=Image.BILINEAR)
        out.append(np.asarray(im, dtype=np.uint8))
    return np.stack(out, axis=0)


def pad_or_trim_T(frames_u8: np.ndarray, expect_t: int) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Make time dimension equal expect_t by trimming or repeating the last frame."""
    t = int(frames_u8.shape[0])
    meta: Dict[str, Any] = {"orig_T": t, "expect_t": int(expect_t), "action": "none"}
    if t == expect_t:
        return frames_u8, meta
    if t > expect_t:
        meta["action"] = "trim"
        return frames_u8[:expect_t], meta
    meta["action"] = "pad_last"
    pad = expect_t - t
    last = frames_u8[-1:]
    frames2 = np.concatenate([frames_u8, np.repeat(last, pad, axis=0)], axis=0)
    return frames2, meta


def preprocess_stack(raw: np.ndarray, expect_t: int, img_size: int, p_lo: float = 1.0, p_hi: float = 99.0) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Full ETF preprocessing pipeline for one raw grayscale stack."""
    u8, clip_meta = percentile_clip_to_u8(raw, p_lo=p_lo, p_hi=p_hi)
    u8 = resize_stack_u8(u8, img_size=img_size)
    u8, t_meta = pad_or_trim_T(u8, expect_t=expect_t)
    return u8, {"clip": clip_meta, "t": t_meta, "img_size": int(img_size)}


def save_proc_npy(proc_dir: Path, eid: str, frames_u8: np.ndarray) -> Path:
    """Save processed uint8 stack to proc_dir/eid.npy."""
    proc_dir.mkdir(parents=True, exist_ok=True)
    out = proc_dir / f"{eid}.npy"
    np.save(out, frames_u8, allow_pickle=False)
    return out
