from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "RetailPOS"
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
#Created by Truong Quang Nghia, David Nghia SWUST

def external_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def env_file_candidates() -> list[Path]:
    candidates = [
        external_root_dir() / ".env",
        PROJECT_ROOT / ".env",
    ]
    unique_candidates: list[Path] = []
    for path in candidates:
        if path not in unique_candidates:
            unique_candidates.append(path)
    return unique_candidates


def load_project_env() -> None:
    env_path = next((path for path in env_file_candidates() if path.exists()), None)
    if env_path is None:
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
            path = external_root_dir() / path
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
