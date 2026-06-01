from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "RetailPOS"
PROJECT_ROOT = Path(__file__).resolve().parent


def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def user_data_dir() -> Path:
    load_project_env()
    base_dir = os.getenv("LOCALAPPDATA")
    if base_dir:
        path = Path(base_dir) / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    load_project_env()
    override = os.getenv("POS_DB_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        path = user_data_dir() / "pos.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir(*parts: str) -> Path:
    path = user_data_dir() / "cache"
    for part in parts:
        clean_part = str(part).strip().strip("/\\")
        if clean_part:
            path = path / clean_part
    path.mkdir(parents=True, exist_ok=True)
    return path
