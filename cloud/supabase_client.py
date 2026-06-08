import os
from dataclasses import dataclass
from typing import Any

from app_paths import env_file_candidates


class SupabaseConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    anon_key: str


def load_local_env() -> None:
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


def get_supabase_settings() -> SupabaseSettings:
    load_local_env()
    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not anon_key:
        raise SupabaseConfigError(
            "Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_ANON_KEY, or create a .env file."
        )
    return SupabaseSettings(url=url, anon_key=anon_key)


def is_supabase_configured() -> bool:
    try:
        get_supabase_settings()
    except SupabaseConfigError:
        return False
    return True


_client: Any | None = None
_client_settings: SupabaseSettings | None = None


def get_supabase_client():
    global _client, _client_settings
    settings = get_supabase_settings()
    if _client is not None and _client_settings == settings:
        return _client

    try:
        from supabase import create_client
    except ImportError as error:
        raise SupabaseConfigError(
            "The supabase package is not installed. Run setup again or install requirements.txt."
        ) from error

    _client = create_client(settings.url, settings.anon_key)
    _client_settings = settings
    return _client


def reset_supabase_client() -> None:
    global _client, _client_settings
    _client = None
    _client_settings = None


def get_access_token() -> str | None:
    try:
        session = get_supabase_client().auth.get_session()
    except Exception:
        return None
    return getattr(session, "access_token", None)
