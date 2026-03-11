#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


REQUIRED_VARS = [
    "PROC_28C5",
    "PROC_25C",
    "SPLIT_28C5",
    "SPLIT_25C",
    "CKPT_CNN_SINGLE",
    "CKPT_MEANPOOL",
    "CKPT_NOCONS",
    "CKPT_FULL",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate required ETF env vars and referenced paths.")
    ap.add_argument("--require", nargs="*", default=REQUIRED_VARS)
    args = ap.parse_args()

    missing = [v for v in args.require if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"[ERR] missing env vars: {', '.join(missing)}")

    for var in args.require:
        path = Path(os.environ[var])
        if not path.exists():
            raise SystemExit(f"[ERR] path from {var} does not exist: {path}")

    print("== check paths ==")
    for var in args.require:
        print(f"[OK] {var} -> {os.environ[var]}")
    print("[OK] env + paths look good")


if __name__ == "__main__":
    main()
