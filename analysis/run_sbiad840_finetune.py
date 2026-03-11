from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run low-shot S-BIAD840 fine-tuning from a released checkpoint.")
    p.add_argument("--model", required=True, choices=["cnn_single", "meanpool", "nocons", "full"])
    p.add_argument("--stage", required=True, choices=["head_only", "temporal_head", "frame_tail1", "frame_tail2", "full_trainable"])
    p.add_argument("--split_json", required=True)
    p.add_argument("--proc_dir", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--init_ckpt", default="")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--num_workers", type=int, default=8)
    p.add_argument("--batch_size", type=int, default=0)
    p.add_argument("--val_batch_size", type=int, default=0)
    p.add_argument("--samples_per_embryo", type=int, default=0)
    p.add_argument("--jitter", type=int, default=-1)
    p.add_argument("--cache_items", type=int, default=-1)
    p.add_argument("--grad_accum", type=int, default=1)
    p.add_argument("--patience", type=int, default=0)
    p.add_argument("--save_every", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto")
    p.add_argument("--lr", type=float, default=0.0)
    p.add_argument("--mem_profile", default="")
    p.add_argument("--ema_decay", type=float, default=0.0)
    p.add_argument("--ema_start_ratio", type=float, default=0.1)
    p.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--init_use_ema", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ema_eval", action=argparse.BooleanOptionalAction, default=False)
    return p.parse_args()


def ckpt_env_key(model: str) -> str:
    return {
        "cnn_single": "CKPT_CNN_SINGLE",
        "meanpool": "CKPT_MEANPOOL",
        "nocons": "CKPT_NOCONS",
        "full": "CKPT_FULL",
    }[model]


def load_dotenv_defaults(repo_root: Path) -> dict[str, str]:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            out[key] = value
    return out


def resolve_ckpt(model: str, init_ckpt: str, dotenv_defaults: dict[str, str]) -> str:
    if init_ckpt:
        return init_ckpt
    env_key = ckpt_env_key(model)
    value = os.environ.get(env_key, "")
    if not value:
        value = dotenv_defaults.get(env_key, "")
    if not value:
        raise SystemExit(f"Missing checkpoint: pass --init_ckpt or set {env_key}")
    return value


def load_ckpt_cfg(path: str) -> dict[str, Any]:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    cfg = ck.get("cfg")
    if not isinstance(cfg, dict):
        raise SystemExit(f"Checkpoint {path} does not contain a cfg dict")
    return cfg


def stage_freeze_args(stage: str) -> list[str]:
    mapping = {
        "head_only": ["--freeze_frame_encoder", "--freeze_temporal"],
        "temporal_head": ["--freeze_frame_encoder"],
        "frame_tail1": ["--freeze_frame_encoder", "--freeze_temporal", "--unfreeze_frame_tail_blocks", "1"],
        "frame_tail2": ["--freeze_frame_encoder", "--freeze_temporal", "--unfreeze_frame_tail_blocks", "2"],
        "full_trainable": [],
    }
    return mapping[stage]


def pick_int(cli_value: int, ck_cfg: dict[str, Any], key: str) -> int:
    return int(cli_value) if cli_value > 0 else int(ck_cfg[key])


def pick_float(cli_value: float, ck_cfg: dict[str, Any], key: str) -> float:
    return float(cli_value) if cli_value > 0 else float(ck_cfg[key])


def pick_optional_int(cli_value: int, ck_cfg: dict[str, Any], key: str) -> int:
    return int(cli_value) if cli_value >= 0 else int(ck_cfg[key])


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    dotenv_defaults = load_dotenv_defaults(repo_root)
    init_ckpt = resolve_ckpt(args.model, args.init_ckpt, dotenv_defaults)
    ck_cfg = load_ckpt_cfg(init_ckpt)

    mem_profile = args.mem_profile or str(ck_cfg.get("mem_profile", "balanced"))
    temporal_mode = str(ck_cfg.get("temporal_mode", "transformer"))
    lambda_diff = float(ck_cfg.get("lambda_diff", 1.0))

    cmd = [
        sys.executable,
        "src/EmbryoTempoFormer.py",
        "train",
        "--proc_dir", args.proc_dir,
        "--split_json", args.split_json,
        "--out_dir", args.out_dir,
        "--epochs", str(int(args.epochs)),
        "--batch_size", str(pick_int(args.batch_size, ck_cfg, "batch_size")),
        "--val_batch_size", str(pick_int(args.val_batch_size, ck_cfg, "val_batch_size")),
        "--num_workers", str(int(args.num_workers)),
        "--samples_per_embryo", str(pick_int(args.samples_per_embryo, ck_cfg, "samples_per_embryo")),
        "--jitter", str(pick_optional_int(args.jitter, ck_cfg, "jitter")),
        "--cache_items", str(pick_optional_int(args.cache_items, ck_cfg, "cache_items")),
        "--lr", str(pick_float(args.lr, ck_cfg, "lr")),
        "--weight_decay", str(float(ck_cfg.get("weight_decay", 0.01))),
        "--warmup_ratio", str(float(ck_cfg.get("warmup_ratio", 0.01))),
        "--lr_min_ratio", str(float(ck_cfg.get("lr_min_ratio", 0.05))),
        "--max_grad_norm", str(float(ck_cfg.get("max_grad_norm", 1.0))),
        "--grad_accum", str(int(args.grad_accum)),
        "--clip_len", str(int(ck_cfg.get("clip_len", 24))),
        "--img_size", str(int(ck_cfg.get("img_size", 384))),
        "--expect_t", str(int(ck_cfg.get("expect_t", 192))),
        "--model_dim", str(int(ck_cfg.get("model_dim", 128))),
        "--model_depth", str(int(ck_cfg.get("model_depth", 4))),
        "--model_heads", str(int(ck_cfg.get("model_heads", 4))),
        "--model_mlp_ratio", str(float(ck_cfg.get("model_mlp_ratio", 2.0))),
        "--drop", str(float(ck_cfg.get("drop", 0.1))),
        "--attn_drop", str(float(ck_cfg.get("attn_drop", 0.0))),
        "--temporal_drop_p", str(float(ck_cfg.get("temporal_drop_p", 0.0))),
        "--temporal_mode", temporal_mode,
        "--cnn_base", str(int(ck_cfg.get("cnn_base", 24))),
        "--cnn_expand", str(int(ck_cfg.get("cnn_expand", 2))),
        "--cnn_se_reduction", str(int(ck_cfg.get("cnn_se_reduction", 4))),
        "--mem_profile", mem_profile,
        "--lambda_abs", str(float(ck_cfg.get("lambda_abs", 1.0))),
        "--lambda_diff", str(lambda_diff),
        "--cons_ramp_ratio", str(float(ck_cfg.get("cons_ramp_ratio", 0.2))),
        "--abs_loss_type", str(ck_cfg.get("abs_loss_type", "l1")),
        "--seed", str(int(args.seed)),
        "--device", args.device,
        "--init_ckpt", init_ckpt,
        "--save_every", str(int(args.save_every)),
        "--patience", str(int(args.patience)),
        "--ema_decay", str(float(args.ema_decay)),
        "--ema_start_ratio", str(float(args.ema_start_ratio)),
    ]

    cmd.append("--amp" if args.amp else "--no-amp")
    cmd.append("--init_use_ema" if args.init_use_ema else "--no-init_use_ema")
    cmd.append("--ema_eval" if args.ema_eval else "--no-ema_eval")
    cmd.extend(stage_freeze_args(args.stage))

    resolved = {
        "model": args.model,
        "stage": args.stage,
        "init_ckpt": init_ckpt,
        "split_json": args.split_json,
        "proc_dir": args.proc_dir,
        "out_dir": args.out_dir,
        "batch_size": pick_int(args.batch_size, ck_cfg, "batch_size"),
        "val_batch_size": pick_int(args.val_batch_size, ck_cfg, "val_batch_size"),
        "samples_per_embryo": pick_int(args.samples_per_embryo, ck_cfg, "samples_per_embryo"),
        "jitter": pick_optional_int(args.jitter, ck_cfg, "jitter"),
        "cache_items": pick_optional_int(args.cache_items, ck_cfg, "cache_items"),
        "lr": pick_float(args.lr, ck_cfg, "lr"),
        "temporal_mode": temporal_mode,
        "lambda_diff": lambda_diff,
        "cnn_base": int(ck_cfg.get("cnn_base", 24)),
        "model_dim": int(ck_cfg.get("model_dim", 128)),
        "model_depth": int(ck_cfg.get("model_depth", 4)),
        "mem_profile": mem_profile,
        "freeze_args": stage_freeze_args(args.stage),
    }
    print(json.dumps(resolved, indent=2, sort_keys=True))
    subprocess.run(cmd, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
