from __future__ import annotations

import os
from pathlib import Path


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


def get_setting(name: str, dotenv_defaults: dict[str, str], default: str = "") -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    value = dotenv_defaults.get(name, "")
    if value:
        return value
    return default


def resolve_path(raw: str, repo_root: Path) -> str:
    path = Path(raw)
    return str(path if path.is_absolute() else (repo_root / path).resolve())
