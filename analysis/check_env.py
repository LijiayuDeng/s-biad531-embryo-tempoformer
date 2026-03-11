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

OPTIONAL_GROUPS = {
    "sbiad840": [
        "PROC_28C5_SBIAD840",
        "PROC_25C_SBIAD840",
        "SPLIT_28C5_SBIAD840",
        "SPLIT_25C_SBIAD840",
    ]
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate required ETF env vars and referenced paths.")
    ap.add_argument("--require", nargs="*", default=REQUIRED_VARS)
    ap.add_argument("--with-optional", nargs="*", default=[])
    args = ap.parse_args()

    require = list(args.require)
    for group in args.with_optional:
        vars_ = OPTIONAL_GROUPS.get(group)
        if vars_ is None:
            raise SystemExit(f"[ERR] unknown optional group: {group}")
        require.extend(vars_)

    missing = [v for v in require if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"[ERR] missing env vars: {', '.join(missing)}")

    for var in require:
        path = Path(os.environ[var])
        if not path.exists():
            raise SystemExit(f"[ERR] path from {var} does not exist: {path}")

    print("== check paths ==")
    for var in require:
        print(f"[OK] {var} -> {os.environ[var]}")
    print("[OK] env + paths look good")


if __name__ == "__main__":
    main()
