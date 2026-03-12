#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EmbryoTempoFormer — clip saliency visualization (SmoothGrad, paper-friendly)

This script visualizes saliency heatmaps for a 24-frame clip and summarizes
per-frame temporal importance. It supports two methods:

1) grad:
   Vanilla input-gradient saliency: |d(t_hat)/d(input)|

2) smoothgrad (recommended):
   SmoothGrad: average saliency over N noisy perturbations of the input, which
   reduces speckle/noise and produces cleaner heatmaps.

Outputs (for each selected start s)
----------------------------------
- saliency_grid_start{s}.png   : 24-frame grid, grayscale + heatmap overlay
- saliency_time_start{s}.png   : per-frame importance curve (0..23)
- saliency_imp_start{s}.npy    : raw per-frame importance values (float)

Additional output
-----------------
- saliency_time_overlay.png    : overlay of the temporal curves for all starts

Important
---------
This is qualitative interpretability. Do not over-claim causality.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
import torch.nn.functional as F

# Make repo root importable so we can `import src...`
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


def load_model_from_ckpt(ckpt_path: str, use_ema: bool, device: torch.device):
    """
    Build the model architecture from checkpoint cfg and load weights.

    We rely on your repo's src/EmbryoTempoFormer.py providing:
      - build_model(cfg)
      - _trainconfig_from_ckpt_cfg(ck_cfg, overrides)
      - _load_ckpt_weights_into_model(model, ckpt_dict, use_ema)
    """
    from src.EmbryoTempoFormer import build_model, _trainconfig_from_ckpt_cfg, _load_ckpt_weights_into_model

    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    ck_cfg = ck.get("cfg", {}) if isinstance(ck, dict) else {}

    overrides = dict(
        proc_dir=ck_cfg.get("proc_dir", ""),
        split_json=ck_cfg.get("split_json", ""),
        out_dir=str(REPO_ROOT / "runs"),
        clip_len=int(ck_cfg.get("clip_len", 24)),
        img_size=int(ck_cfg.get("img_size", 384)),
        expect_t=int(ck_cfg.get("expect_t", 192)),
        mem_profile=str(ck_cfg.get("mem_profile", "balanced")),
        amp=False,  # keep OFF for stable gradients in saliency
        device=str(device),
    )
    cfg = _trainconfig_from_ckpt_cfg(ck_cfg, overrides)
    model = build_model(cfg).to(device)
    _load_ckpt_weights_into_model(model, ck, use_ema=use_ema)
    model.eval()
    return model, cfg


def pick_five_starts(T: int, L: int) -> List[int]:
    """
    Choose five starts: early / early-mid / mid / mid-late / late
    on the valid start interval [0, T-L].
    """
    max_start = max(0, T - L)
    return [0, max_start // 4, max_start // 2, (3 * max_start) // 4, max_start]


def smooth2d_np(a01: np.ndarray, k: int = 9) -> np.ndarray:
    """Avg-pool blur for a [0,1] heatmap; reduces speckle."""
    if k <= 1:
        return a01.astype(np.float32)
    t = torch.from_numpy(a01[None, None]).float()
    t = F.avg_pool2d(t, kernel_size=k, stride=1, padding=k // 2)
    return t[0, 0].numpy().astype(np.float32)


def norm_perc(a: np.ndarray, lo: float = 95.0, hi: float = 99.9, gamma: float = 0.7) -> np.ndarray:
    """
    Percentile stretch + gamma to make heavy-tailed saliency visible.

    a: [H,W] nonnegative
    returns: [H,W] in [0,1]
    """
    a = a.astype(np.float32)
    v0 = np.percentile(a, lo)
    v1 = np.percentile(a, hi)
    if v1 <= v0 + 1e-12:
        return np.zeros_like(a, dtype=np.float32)
    z = np.clip((a - v0) / (v1 - v0 + 1e-12), 0.0, 1.0)
    return (z ** gamma).astype(np.float32)


def alpha_from_hm(hm01: np.ndarray, thr: float = 0.50, alpha_max: float = 0.95, alpha_gamma: float = 1.2) -> np.ndarray:
    """
    Pixel-wise alpha mask to hide low-saliency pixels.

    hm01: [H,W] in [0,1]
    """
    hm01 = hm01.astype(np.float32)
    z = np.clip((hm01 - thr) / (1.0 - thr + 1e-12), 0.0, 1.0)
    z = (z ** alpha_gamma).astype(np.float32)
    return np.clip(z * alpha_max, 0.0, alpha_max).astype(np.float32)


def forward_t(model, x: torch.Tensor, use_amp: bool) -> torch.Tensor:
    """
    Forward pass returning scalar prediction with gradients ENABLED.

    Critical detail:
    - torch.enable_grad() does NOT override torch.inference_mode().
    - We explicitly disable inference_mode here to avoid "no grad_fn" errors.
    """
    with torch.inference_mode(False):
        with torch.enable_grad():
            if x.device.type == "cuda":
                with torch.cuda.amp.autocast(enabled=use_amp):
                    y = model(x)
            else:
                y = model(x)
    return y[0]


def compute_saliency(
    model,
    x0: torch.Tensor,
    method: str,
    use_amp: bool,
    sg_N: int,
    sg_sigma: float,
) -> Tuple[torch.Tensor, float, float]:
    """
    Compute saliency g = |d t_hat / d x| for x0.

    Returns:
      g      : [1,L,1,H,W] float abs-grad (averaged if smoothgrad)
      t_mean : mean predicted time across noise samples (for smoothgrad)
      t_std  : std predicted time across noise samples (for smoothgrad), else 0
    """
    method = method.lower()
    if method not in ("grad", "smoothgrad"):
        raise ValueError("method must be grad or smoothgrad")

    if method == "grad":
        x = x0.detach().clone()
        x.requires_grad_(True)

        t = forward_t(model, x, use_amp)

        model.zero_grad(set_to_none=True)
        if x.grad is not None:
            x.grad.zero_()

        if not t.requires_grad:
            raise RuntimeError(
                f"t has no grad_fn (grad_enabled={torch.is_grad_enabled()}, "
                f"inference_mode={torch.is_inference_mode_enabled()})"
            )

        t.backward()
        g = x.grad.detach().abs().float()
        return g, float(t.detach().cpu()), 0.0

    # smoothgrad
    N = int(sg_N)
    sigma = float(sg_sigma)
    if N <= 1:
        return compute_saliency(model, x0, "grad", use_amp, sg_N, sg_sigma)

    g_acc = None
    t_list: List[float] = []

    for _ in range(N):
        noise = torch.randn_like(x0) * sigma
        x = (x0 + noise).clamp(0.0, 1.0).detach()
        x.requires_grad_(True)

        t = forward_t(model, x, use_amp)
        t_list.append(float(t.detach().cpu()))

        model.zero_grad(set_to_none=True)
        if x.grad is not None:
            x.grad.zero_()

        if not t.requires_grad:
            raise RuntimeError(
                f"t has no grad_fn (grad_enabled={torch.is_grad_enabled()}, "
                f"inference_mode={torch.is_inference_mode_enabled()})"
            )

        t.backward()

        g = x.grad.detach().abs().float()
        g_acc = g if g_acc is None else (g_acc + g)

    g_mean = g_acc / float(N)
    t_mean = float(np.mean(t_list))
    t_std = float(np.std(t_list, ddof=0))
    return g_mean, t_mean, t_std


def run_one_start(
    model,
    frames_u8: np.ndarray,
    start: int,
    clip_len: int,
    device: torch.device,
    method: str,
    use_amp: bool,
    sg_N: int,
    sg_sigma: float,
    hm_lo: float,
    hm_hi: float,
    hm_gamma: float,
    blur_k: int,
) -> Tuple[int, np.ndarray, np.ndarray, np.ndarray, float, float]:
    """
    Compute saliency for one clip start.

    Returns:
      s      : actual start (clipped to valid range)
      clip   : [L,H,W] uint8
      hm_vis : [L,H,W] float in [0,1] (visual heatmaps)
      imp    : [L] float raw per-frame importance (mean abs grad)
      t_mean : float predicted time mean
      t_std  : float predicted time std (smoothgrad only)
    """
    T, H, W = frames_u8.shape
    s = int(start)
    L = int(clip_len)
    max_start = max(0, T - L)
    s = int(np.clip(s, 0, max_start))

    clip = frames_u8[s:s + L]
    if clip.shape[0] < L:
        pad = L - clip.shape[0]
        clip = np.concatenate([clip, np.repeat(clip[-1:], pad, axis=0)], axis=0)

    x0 = torch.from_numpy(np.ascontiguousarray(clip)).float() / 255.0
    x0 = x0.unsqueeze(0).unsqueeze(2).to(device)

    g, t_mean, t_std = compute_saliency(model, x0, method, use_amp, sg_N, sg_sigma)

    g_np = g[0, :, 0].detach().cpu().numpy().astype(np.float32)  # [L,H,W]
    imp = g_np.reshape(L, -1).mean(axis=1).astype(np.float32)

    hm_list = []
    for i in range(L):
        h01 = norm_perc(g_np[i], lo=hm_lo, hi=hm_hi, gamma=hm_gamma)
        h01 = smooth2d_np(h01, k=blur_k)
        hm_list.append(h01)
    hm_vis = np.stack(hm_list, axis=0)

    return s, clip, hm_vis, imp, t_mean, t_std


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--npy", required=True, help="processed uint8 npy [T,H,W]")
    ap.add_argument("--clip_len", type=int, default=24)

    # starts
    ap.add_argument("--five", action="store_true", help="use five starts: early/early-mid/mid/mid-late/late")
    ap.add_argument("--starts", default="", help="comma-separated starts, e.g. '0,42,84,126,168'")
    ap.add_argument("--start", type=int, default=0, help="single start (used if not --five/--starts)")

    # method
    ap.add_argument("--method", default="smoothgrad", choices=["grad", "smoothgrad"])
    ap.add_argument("--sg_N", type=int, default=20, help="SmoothGrad samples (ignored for grad)")
    ap.add_argument("--sg_sigma", type=float, default=0.01, help="SmoothGrad noise std on [0,1] input")

    # viz tuning
    ap.add_argument("--hm_lo", type=float, default=95.0)
    ap.add_argument("--hm_hi", type=float, default=99.9)
    ap.add_argument("--hm_gamma", type=float, default=0.7)
    ap.add_argument("--blur_k", type=int, default=9)
    ap.add_argument("--alpha_thr", type=float, default=0.50)
    ap.add_argument("--alpha_max", type=float, default=0.95)

    # runtime
    ap.add_argument("--out_dir", default="runs/vis")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--use_ema", action="store_true")
    ap.add_argument("--amp", action="store_true", help="enable AMP (default OFF for stable gradients)")
    ap.add_argument("--dpi", type=int, default=220)
    args = ap.parse_args()

    device = torch.device(
        "cuda" if (args.device == "auto" and torch.cuda.is_available())
        else (args.device if args.device != "auto" else "cpu")
    )
    use_amp = bool(args.amp) and (device.type == "cuda")

    os.makedirs(args.out_dir, exist_ok=True)

    frames = np.load(args.npy, mmap_mode=None)
    if frames.ndim != 3 or frames.dtype != np.uint8:
        raise ValueError(f"Expected uint8 [T,H,W], got {frames.dtype} {frames.shape}")
    T, H, W = frames.shape

    if args.five:
        starts = pick_five_starts(T, args.clip_len)
    elif args.starts.strip():
        starts = [int(x.strip()) for x in args.starts.split(",") if x.strip()]
    else:
        starts = [int(args.start)]

    model, cfg = load_model_from_ckpt(args.ckpt, args.use_ema, device)

    import matplotlib.pyplot as plt

    overlay_data = []  # (start, imp01, t_mean, t_std)

    for s_req in starts:
        s, clip, hm_vis, imp, t_mean, t_std = run_one_start(
            model=model,
            frames_u8=frames,
            start=s_req,
            clip_len=args.clip_len,
            device=device,
            method=args.method,
            use_amp=use_amp,
            sg_N=args.sg_N,
            sg_sigma=args.sg_sigma,
            hm_lo=args.hm_lo,
            hm_hi=args.hm_hi,
            hm_gamma=args.hm_gamma,
            blur_k=args.blur_k,
        )

        # normalize per-frame importance within this clip for plotting
        imp01 = imp.copy()
        if float(np.max(imp01)) > 1e-12:
            imp01 = (imp01 - imp01.min()) / (imp01.max() - imp01.min() + 1e-12)
        else:
            imp01[:] = 0.0

        overlay_data.append((s, imp01, t_mean, t_std))

        # grid overlay
        L = args.clip_len
        ncol = 6
        nrow = int(np.ceil(L / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 2.25, nrow * 2.25))
        axes = np.array(axes).reshape(nrow, ncol)

        for i in range(nrow * ncol):
            r, c = divmod(i, ncol)
            ax = axes[r, c]
            ax.axis("off")
            if i >= L:
                continue

            img = clip[i].astype(np.float32) / 255.0
            hm = hm_vis[i]
            a = alpha_from_hm(hm, thr=float(args.alpha_thr), alpha_max=float(args.alpha_max), alpha_gamma=1.2)

            ax.imshow(img, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
            ax.imshow(hm, cmap="turbo", alpha=a, vmin=0, vmax=1, interpolation="nearest")
            ax.set_title(f"t={s+i}", fontsize=8)

        extra = f" ±{t_std:.3f}" if (args.method == "smoothgrad" and args.sg_N > 1) else ""
        fig.suptitle(f"{args.method} overlay | start={s}, t_hat={t_mean:.3f}{extra}h", fontsize=12)

        out1 = os.path.join(args.out_dir, f"saliency_grid_start{s}.png")
        plt.tight_layout()
        plt.savefig(out1, dpi=args.dpi)
        plt.close(fig)

        # time importance
        fig = plt.figure(figsize=(7.4, 2.7))
        plt.plot(np.arange(L), imp01, marker="o")
        plt.ylim(-0.02, 1.02)
        plt.xlabel("frame index within clip (0..23)")
        plt.ylabel("normalized saliency mass (within clip)")
        plt.title(f"Temporal importance ({args.method}, start={s})")
        plt.grid(True, alpha=0.3)
        out2 = os.path.join(args.out_dir, f"saliency_time_start{s}.png")
        plt.tight_layout()
        plt.savefig(out2, dpi=args.dpi)
        plt.close(fig)

        np.save(os.path.join(args.out_dir, f"saliency_imp_start{s}.npy"), imp)

        print("WROTE:", out1)
        print("WROTE:", out2)
        print(f"t_hat(hpf): mean={t_mean:.3f} std={t_std:.3f} start={s} method={args.method}")

    # overlay curves
    if len(overlay_data) >= 2:
        fig = plt.figure(figsize=(8.2, 3.2))
        for s, imp01, t_mean, t_std in overlay_data:
            lab = f"start={s}, t_hat={t_mean:.2f}"
            if args.method == "smoothgrad" and args.sg_N > 1:
                lab += f"±{t_std:.2f}"
            plt.plot(np.arange(args.clip_len), imp01, marker="o", label=lab)
        plt.ylim(-0.02, 1.02)
        plt.xlabel("frame index within clip (0..23)")
        plt.ylabel("normalized saliency mass (within clip)")
        plt.title(f"Temporal importance overlay ({args.method})")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8, loc="best")
        out3 = os.path.join(args.out_dir, "saliency_time_overlay.png")
        plt.tight_layout()
        plt.savefig(out3, dpi=args.dpi)
        plt.close(fig)
        print("WROTE:", out3)

    print("[DONE] out_dir:", args.out_dir)
    print("NOTE: SmoothGrad is slower; reduce --sg_N for speed if needed.")


if __name__ == "__main__":
    main()
