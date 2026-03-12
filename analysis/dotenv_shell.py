#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description='Emit shell exports from .env without overriding existing env vars.')
    ap.add_argument('--env-file', default='.env')
    args = ap.parse_args()
    env_path = Path(args.env_file)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if os.environ.get(key, ''):
            continue
        print(f"export {key}={shlex.quote(value)}")


if __name__ == '__main__':
    main()
