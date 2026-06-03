from __future__ import annotations

import json
import time
from typing import Any

from supabase_functions.errors import FunctionsError

from .supabase_client import get_access_token, get_supabase_client


class CloudAuthError(RuntimeError):
    pass


SUPABASE_SCHEMA_HINT = (
    "Supabase schema is not installed on this project. "
    "Run `npx supabase db push` after linking the new Supabase project, then try again."
)


def _data_or_raise(response: Any, action: str) -> Any:
    error = getattr(response, "error", None)
    if error:
        raise CloudAuthError(f"Supabase {action} failed: {error}")
    return getattr(response, "data", None)


def _user_id_from_auth_response(response: Any) -> str | None:
    user = getattr(response, "user", None)
    if user is not None:
        return str(getattr(user, "id", "") or "") or None
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        user_data = data.get("user") or {}
        return str(user_data.get("id") or "") or None
    return None


def current_auth_user_id() -> str | None:
    try:
        response = get_supabase_client().auth.get_user()
    except Exception:
        return None
    user = getattr(response, "user", None)
    if user is not None:
        return str(getattr(user, "id", "") or "") or None
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        user_data = data.get("user") or {}
        return str(user_data.get("id") or "") or None
    return None


def current_session_tokens() -> dict[str, str]:
    try:
        session = get_supabase_client().auth.get_session()
    except Exception:
        return {}
    if session is None:
        return {}

    access_token = str(getattr(session, "access_token", "") or "")
    refresh_token = str(getattr(session, "refresh_token", "") or "")
    expires_at = str(getattr(session, "expires_at", "") or "")
    tokens: dict[str, str] = {}
    if access_token:
        tokens["access_token"] = access_token
    if refresh_token:
        tokens["refresh_token"] = refresh_token
    if expires_at:
        tokens["expires_at"] = expires_at
    return tokens


def restore_session(access_token: str | None, refresh_token: str | None) -> str:
    clean_access_token = (access_token or "").strip()
    clean_refresh_token = (refresh_token or "").strip()
    if not clean_access_token and not clean_refresh_token:
        raise CloudAuthError("Missing remembered Supabase session.")

    client = get_supabase_client()
    try:
        if clean_access_token:
            response = client.auth.set_session(clean_access_token, clean_refresh_token)
        else:
            response = client.auth.refresh_session(clean_refresh_token)
    except Exception as error:
        raise CloudAuthError("Remembered Supabase session expired. Please log in again.") from error

    auth_user_id = _user_id_from_auth_response(response) or current_auth_user_id()
    if not auth_user_id:
        raise CloudAuthError("Could not restore remembered Supabase session.")
    return auth_user_id


def _session_from_auth_response(response: Any) -> Any | None:
    session = getattr(response, "session", None)
    if session is not None:
        return session
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return data.get("session")
    return None


def _normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    role = profile.get("roles") or profile.get("role") or {}
    store = profile.get("stores") or profile.get("store") or {}
    if isinstance(role, list):
        role = role[0] if role else {}
    if isinstance(store, list):
        store = store[0] if store else {}
    if not isinstance(role, dict):
        role = {}
    if not isinstance(store, dict):
        store = {}
    role_name = role.get("name") or profile.get("role_name") or "Cashier"
    permissions = role.get("permissions") or profile.get("permissions") or ""
    return {
        "cloud_auth_id": str(profile.get("auth_user_id") or profile.get("id") or ""),
        "store_id": str(profile.get("store_id") or ""),
        "store_name": str(store.get("name") or profile.get("store_name") or ""),
        "email": str(profile.get("email") or ""),
        "username": str(profile.get("email") or ""),
        "full_name": str(profile.get("full_name") or profile.get("email") or ""),
        "role_id": profile.get("role_id"),
        "role_name": str(role_name),
        "permissions": str(permissions),
        "active": bool(profile.get("active", True)),
        "deleted_at": profile.get("deleted_at"),
    }


def _with_role_payload(client: Any, profile: dict[str, Any]) -> dict[str, Any]:
    role = profile.get("roles") or profile.get("role")
    if isinstance(role, dict) and role.get("name"):
        return profile

    role_id = profile.get("role_id")
    if not role_id:
        return profile

    response = (
        client.table("roles")
        .select("id,name,permissions")
        .eq("id", role_id)
        .limit(1)
        .execute()
    )
    role_rows = _data_or_raise(response, "role lookup")
    role_data = role_rows[0] if isinstance(role_rows, list) and role_rows else None
    if isinstance(role_data, dict):
        profile = dict(profile)
        profile["roles"] = role_data
    return profile


def _fetch_profile_row(client: Any, auth_user_id: str) -> dict[str, Any] | None:
    response = (
        client.table("profiles")
        .select("auth_user_id,store_id,email,full_name,role_id,active,deleted_at,roles(id,name,permissions),stores(id,name)")
        .eq("auth_user_id", auth_user_id)
        .limit(1)
        .execute()
    )
    rows = _data_or_raise(response, "profile lookup")
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    return row if isinstance(row, dict) else None


def ensure_owner_profile(required: bool = False) -> dict[str, Any]:
    client = get_supabase_client()
    try:
        response = client.rpc("ensure_owner_profile").execute()
        data = _data_or_raise(response, "owner profile repair")
        return data if isinstance(data, dict) else {}
    except Exception as error:
        if required:
            raise CloudAuthError(
                "Could not repair the owner Admin profile. "
                f"{SUPABASE_SCHEMA_HINT} "
                f"Details: {error}"
            ) from error
        return {}


def ensure_registered_store_owner(store_name: str, full_name: str, required: bool = False) -> dict[str, Any]:
    client = get_supabase_client()
    try:
        response = client.rpc(
            "ensure_registered_store_owner",
            {
                "p_store_name": store_name.strip(),
                "p_full_name": full_name.strip(),
            },
        ).execute()
        data = _data_or_raise(response, "registered owner profile repair")
        return data if isinstance(data, dict) else {}
    except Exception as error:
        if required:
            raise CloudAuthError(
                "Could not create the owner Admin profile. "
                f"{SUPABASE_SCHEMA_HINT} "
                f"Details: {error}"
            ) from error
        return {}


def fetch_profile(auth_user_id: str | None = None) -> dict[str, Any]:
    client = get_supabase_client()
    if auth_user_id is None:
        user_response = client.auth.get_user()
        user = getattr(user_response, "user", None)
        if user is None:
            raise CloudAuthError("Could not read the current Supabase user.")
        auth_user_id = str(getattr(user, "id", "") or "")

    profile = None
    for attempt in range(5):
        profile = _fetch_profile_row(client, auth_user_id)
        if profile is not None:
            break
        if attempt < 4:
            time.sleep(0.4)
    if profile is None:
        raise CloudAuthError(
            "Could not find a POS profile for this Supabase account. "
            f"{SUPABASE_SCHEMA_HINT}"
        )

    profile = _with_role_payload(client, profile)
    normalized = _normalize_profile(profile)
    if not normalized["active"]:
        raise CloudAuthError("This account is inactive.")
    if not normalized["store_id"]:
        raise CloudAuthError("This account is not assigned to a store.")
    return normalized


def login(email: str, password: str) -> dict[str, Any]:
    client = get_supabase_client()
    response = client.auth.sign_in_with_password(
        {
            "email": email.strip(),
            "password": password,
        }
    )
    auth_user_id = _user_id_from_auth_response(response)
    if not auth_user_id:
        raise CloudAuthError("Supabase login did not return a user.")
    ensure_owner_profile()
    return fetch_profile(auth_user_id)


def register_store_owner(store_name: str, full_name: str, email: str, password: str) -> dict[str, Any]:
    client = get_supabase_client()
    response = client.auth.sign_up(
        {
            "email": email.strip(),
            "password": password,
            "options": {
                "data": {
                    "store_name": store_name.strip(),
                    "full_name": full_name.strip(),
                }
            },
        }
    )
    auth_user_id = _user_id_from_auth_response(response)
    if not auth_user_id:
        raise CloudAuthError("Supabase registration did not return a user.")

    if _session_from_auth_response(response) is None:
        try:
            login_response = client.auth.sign_in_with_password(
                {
                    "email": email.strip(),
                    "password": password,
                }
            )
        except Exception as error:
            raise CloudAuthError(
                "Supabase created the account but did not return a login session. "
                "For this desktop app, disable email confirmations in Supabase Auth settings "
                "or confirm the email, then log in again. "
                f"Details: {error}"
            ) from error
        auth_user_id = _user_id_from_auth_response(login_response) or auth_user_id
    ensure_registered_store_owner(store_name, full_name, required=True)
    profile = fetch_profile(auth_user_id)
    if profile["role_name"] != "Admin":
        raise CloudAuthError(
            f"Store owner registration returned role '{profile['role_name']}', not Admin. "
            f"{SUPABASE_SCHEMA_HINT} "
            "If this email already exists in Supabase Auth, delete that Auth user or use a new email."
        )
    return profile


def list_store_users() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = (
        client
        .table("profiles")
        .select("auth_user_id,store_id,email,full_name,role_id,active,deleted_at,roles(id,name,permissions),stores(id,name)")
        .order("created_at", desc=True)
        .execute()
    )
    rows = _data_or_raise(response, "user list")
    if not isinstance(rows, list):
        return []
    return [_normalize_profile(_with_role_payload(client, row)) for row in rows if isinstance(row, dict)]


def invoke_admin_function(function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = get_access_token()
    options: dict[str, Any] = {"body": payload, "responseType": "json"}
    if token:
        options["headers"] = {"Authorization": f"Bearer {token}"}
    try:
        data = get_supabase_client().functions.invoke(function_name, invoke_options=options)
    except FunctionsError as error:
        raise CloudAuthError(f"{function_name} failed: {error.message}") from error
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CloudAuthError(f"{function_name} returned unreadable bytes: {data[:120]!r}") from error
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as error:
            preview = data[:240] + ("..." if len(data) > 240 else "")
            raise CloudAuthError(f"{function_name} returned invalid JSON: {preview}") from error
    if not isinstance(data, dict):
        raise CloudAuthError(f"{function_name} returned an invalid payload: {type(data).__name__}")
    if data.get("error"):
        raise CloudAuthError(str(data["error"]))
    profile = data.get("profile")
    return _normalize_profile(_with_role_payload(get_supabase_client(), profile)) if isinstance(profile, dict) else data


def admin_create_user(email: str, password: str, full_name: str, role_name: str) -> dict[str, Any]:
    return invoke_admin_function(
        "admin-create-user",
        {
            "email": email.strip(),
            "password": password,
            "full_name": full_name.strip(),
            "role_name": role_name,
        },
    )


def admin_update_user(
    auth_user_id: str,
    email: str,
    full_name: str,
    role_name: str,
    password: str | None = None,
    active: bool = True,
    deleted_at: str | None = None,
    include_deleted_at: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "auth_user_id": auth_user_id,
        "email": email.strip(),
        "full_name": full_name.strip(),
        "role_name": role_name,
        "active": active,
    }
    if deleted_at is not None or include_deleted_at:
        payload["deleted_at"] = deleted_at
    if password:
        payload["password"] = password
    return invoke_admin_function("admin-update-user", payload)


def sign_out() -> None:
    get_supabase_client().auth.sign_out()
