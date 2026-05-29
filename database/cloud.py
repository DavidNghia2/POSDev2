import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DB_PATH = PROJECT_ROOT / "pos.db"
DEFAULT_SUPABASE_URL = "https://teqfqsgakcxuafkzxelm.supabase.co"
REQUEST_TIMEOUT_SECONDS = 8
_runtime_disabled = False
_settings_cache: dict[str, str | None] = {}


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue
        key, value = clean_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")


def supabase_key() -> str:
    return os.environ.get("SUPABASE_ANON_KEY", "").strip()


def is_enabled() -> bool:
    if _runtime_disabled:
        return False
    key = supabase_key()
    return bool(supabase_url() and key and not key.startswith("replace-with"))


def disable_for_process() -> None:
    global _runtime_disabled
    _runtime_disabled = True


def enable_for_process() -> None:
    global _runtime_disabled
    _runtime_disabled = False


class SupabaseError(RuntimeError):
    pass


class SupabaseRest:
    def __init__(self) -> None:
        if not is_enabled():
            raise SupabaseError("Supabase is not configured. Add SUPABASE_ANON_KEY to .env.")
        self.base_url = f"{supabase_url()}/rest/v1"
        self.key = supabase_key()

    def request(
        self,
        method: str,
        table: str,
        query: list[tuple[str, str]] | None = None,
        payload: Any | None = None,
        prefer: str = "return=representation",
    ) -> Any:
        query_string = urllib.parse.urlencode(query or [], doseq=True, safe="(),.*:")
        url = f"{self.base_url}/{table}"
        if query_string:
            url = f"{url}?{query_string}"

        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("apikey", self.key)
        request.add_header("Authorization", f"Bearer {self.key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        request.add_header("Prefer", prefer)

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                data = response.read().decode("utf-8")
                return json.loads(data) if data else None
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise SupabaseError(f"Supabase {method} {table} failed: {error.code} {details}") from error
        except urllib.error.URLError as error:
            disable_for_process()
            raise SupabaseError(f"Could not connect to Supabase: {error.reason}") from error

    def select(self, table: str, query: list[tuple[str, str]] | None = None) -> list[dict[str, Any]]:
        return self.request("GET", table, query=query) or []

    def insert(self, table: str, rows: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.request("POST", table, payload=rows) or []

    def update(
        self,
        table: str,
        values: dict[str, Any],
        query: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        return self.request("PATCH", table, query=query, payload=values) or []

    def delete(self, table: str, query: list[tuple[str, str]]) -> None:
        self.request("DELETE", table, query=query, prefer="return=minimal")


def client() -> SupabaseRest:
    return SupabaseRest()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def local_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(LOCAL_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_local_sync_queue() -> None:
    with local_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                operation TEXT NOT NULL,
                payload TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                synced_at TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue (status)")
        connection.commit()


def queue_offline_operation(
    entity_type: str,
    entity_id: int | None,
    operation: str,
    payload: dict[str, Any],
) -> None:
    ensure_local_sync_queue()
    with local_connection() as connection:
        connection.execute(
            """
            INSERT INTO sync_queue (entity_type, entity_id, operation, payload, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (entity_type, entity_id, operation, json.dumps(payload)),
        )
        connection.commit()


def pending_sync_count() -> int:
    ensure_local_sync_queue()
    with local_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM sync_queue WHERE status = 'pending'"
        ).fetchone()
        return int(row["count"] if row else 0)


def can_connect() -> bool:
    if not supabase_key() or supabase_key().startswith("replace-with"):
        return False
    enable_for_process()
    try:
        client().select("roles", [("select", "id"), ("limit", "1")])
        return True
    except SupabaseError:
        return False


def hash_password(password: str) -> str:
    import hashlib

    return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_auth_db() -> None:
    api = client()
    if not api.select("roles", [("select", "id"), ("limit", "1")]):
        api.insert(
            "roles",
            [
                {"id": 1, "name": "Admin", "permissions": "all"},
                {"id": 2, "name": "Manager", "permissions": "sales,reports,products,registers,shifts,reconciliation"},
                {"id": 3, "name": "Cashier", "permissions": "sales,shifts"},
            ],
        )

    if not api.select("users", [("select", "id"), ("limit", "1")]):
        api.insert(
            "users",
            [
                {"username": "admin", "password_hash": hash_password("admin123"), "full_name": "Administrator", "role_id": 1},
                {"username": "manager", "password_hash": hash_password("manager123"), "full_name": "Store Manager", "role_id": 2},
                {"username": "cashier", "password_hash": hash_password("cashier123"), "full_name": "Cashier", "role_id": 3},
            ],
        )

    if not api.select("registers", [("select", "id"), ("limit", "1")]):
        api.insert("registers", {"name": "Main Register", "location": "Store Front"})


def init_db() -> None:
    init_auth_db()
    seed_products_from_local_sqlite()


def seed_products_from_local_sqlite() -> None:
    api = client()
    if api.select("products", [("select", "id"), ("limit", "1")]):
        return
    if not LOCAL_DB_PATH.exists():
        return

    connection = sqlite3.connect(LOCAL_DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        products = connection.execute(
            """
            SELECT id, barcode, sku, name, price, category, stock_qty,
                   requires_weight, active, image_path
            FROM products
            ORDER BY id
            """
        ).fetchall()
        if not products:
            return
        product_rows = [
            {
                "id": row["id"],
                "barcode": row["barcode"],
                "sku": row["sku"],
                "name": row["name"],
                "price": row["price"],
                "category": row["category"],
                "stock_qty": row["stock_qty"] or 0,
                "requires_weight": bool(row["requires_weight"]),
                "active": bool(row["active"]),
                "image_path": row["image_path"],
            }
            for row in products
        ]
        api.insert("products", product_rows)

        barcode_rows = connection.execute(
            """
            SELECT id, product_id, barcode, is_primary
            FROM product_barcodes
            ORDER BY id
            """
        ).fetchall()
        if barcode_rows:
            api.insert(
                "product_barcodes",
                [
                    {
                        "id": row["id"],
                        "product_id": row["product_id"],
                        "barcode": row["barcode"],
                        "is_primary": bool(row["is_primary"]),
                    }
                    for row in barcode_rows
                ],
            )
    finally:
        connection.close()


def with_role(user: dict[str, Any]) -> dict[str, Any]:
    if not user.get("role_id"):
        user["role_name"] = None
        user["permissions"] = ""
        return user
    roles = client().select("roles", [("select", "name,permissions"), ("id", f"eq.{user['role_id']}"), ("limit", "1")])
    role = roles[0] if roles else {}
    user["role_name"] = role.get("name")
    user["permissions"] = role.get("permissions", "")
    return user


def get_all_roles() -> list[dict[str, Any]]:
    init_auth_db()
    return client().select("roles", [("select", "id,name,permissions"), ("order", "id.asc")])


def get_all_users() -> list[dict[str, Any]]:
    init_auth_db()
    users = client().select("users", [("select", "id,username,full_name,role_id,active,created_at"), ("order", "id.desc")])
    return [with_role(user) for user in users]


def get_user_by_username(username: str) -> dict[str, Any] | None:
    init_auth_db()
    rows = client().select(
        "users",
        [("select", "id,username,password_hash,full_name,role_id,active"), ("username", f"eq.{username}"), ("active", "eq.true"), ("limit", "1")],
    )
    return with_role(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    init_auth_db()
    rows = client().select(
        "users",
        [("select", "id,username,password_hash,full_name,role_id,active"), ("id", f"eq.{user_id}"), ("active", "eq.true"), ("limit", "1")],
    )
    return with_role(rows[0]) if rows else None


def get_all_registers() -> list[dict[str, Any]]:
    init_auth_db()
    return client().select("registers", [("select", "id,name,location,active"), ("active", "eq.true"), ("order", "id.asc")])


def get_open_shift(register_id: int) -> dict[str, Any] | None:
    rows = client().select(
        "cash_shifts",
        [
            ("select", "id,register_id,user_id,opened_at,opening_balance,status"),
            ("register_id", f"eq.{register_id}"),
            ("status", "eq.open"),
            ("order", "id.desc"),
            ("limit", "1"),
        ],
    )
    return rows[0] if rows else None


def open_cash_shift(register_id: int, user_id: int, opening_balance: float = 0) -> int:
    existing = get_open_shift(register_id)
    if existing:
        return int(existing["id"])
    rows = client().insert(
        "cash_shifts",
        {
            "register_id": register_id,
            "user_id": user_id,
            "opening_balance": opening_balance,
            "expected_balance": opening_balance,
            "status": "open",
        },
    )
    shift_id = int(rows[0]["id"])
    add_cash_movement(shift_id, user_id, "open", opening_balance, "Opening balance")
    return shift_id


def add_cash_movement(shift_id: int, user_id: int, movement_type: str, amount: float, reason: str) -> None:
    api = client()
    api.insert(
        "cash_movements",
        {"shift_id": shift_id, "user_id": user_id, "type": movement_type, "amount": amount, "reason": reason},
    )
    rows = api.select("cash_shifts", [("select", "expected_balance,opening_balance"), ("id", f"eq.{shift_id}"), ("limit", "1")])
    if rows:
        delta = amount if movement_type in {"open", "cash_in", "sale"} else -amount
        current = rows[0].get("expected_balance")
        if current is None:
            current = rows[0].get("opening_balance") or 0
        api.update("cash_shifts", {"expected_balance": float(current) + delta}, [("id", f"eq.{shift_id}"), ("status", "eq.open")])


def close_cash_shift(shift_id: int, user_id: int, closing_balance: float) -> None:
    api = client()
    api.update(
        "cash_shifts",
        {"closed_at": now_iso(), "closing_balance": closing_balance, "status": "closed"},
        [("id", f"eq.{shift_id}"), ("status", "eq.open")],
    )
    api.insert(
        "cash_movements",
        {"shift_id": shift_id, "user_id": user_id, "type": "close", "amount": closing_balance, "reason": "Closing balance"},
    )


def add_user(username: str, password: str, full_name: str, role_id: int) -> int:
    if client().select("users", [("select", "id"), ("username", f"eq.{username}"), ("limit", "1")]):
        raise ValueError("That username is already in use.")
    rows = client().insert(
        "users",
        {"username": username, "password_hash": hash_password(password), "full_name": full_name, "role_id": role_id},
    )
    return int(rows[0]["id"])


def update_user(user_id: int, username: str, full_name: str, role_id: int, new_password: str | None = None) -> None:
    duplicate = client().select("users", [("select", "id"), ("username", f"eq.{username}"), ("id", f"neq.{user_id}"), ("limit", "1")])
    if duplicate:
        raise ValueError("That username is already in use.")
    values = {"username": username, "full_name": full_name, "role_id": role_id}
    if new_password:
        values["password_hash"] = hash_password(new_password)
    client().update("users", values, [("id", f"eq.{user_id}")])


def delete_user(user_id: int, current_user_id: int | None = None) -> None:
    if current_user_id is not None and user_id == current_user_id:
        raise ValueError("You cannot delete the account you are currently using.")
    client().delete("users", [("id", f"eq.{user_id}")])


def add_register(name: str, location: str) -> int:
    rows = client().insert("registers", {"name": name, "location": location})
    return int(rows[0]["id"])


def update_register(register_id: int, name: str, location: str) -> None:
    client().update("registers", {"name": name, "location": location}, [("id", f"eq.{register_id}")])


def delete_register(register_id: int) -> None:
    client().update("registers", {"active": False}, [("id", f"eq.{register_id}")])


def log_audit(
    user_id: int,
    action: str,
    table_name: str | None = None,
    record_id: int | None = None,
    old_values: str | None = None,
    new_values: str | None = None,
) -> None:
    client().insert(
        "audit_logs",
        {
            "user_id": user_id,
            "action": action,
            "table_name": table_name,
            "record_id": record_id,
            "old_values": old_values,
            "new_values": new_values,
        },
    )


def get_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    logs = client().select(
        "audit_logs",
        [("select", "id,action,table_name,record_id,old_values,new_values,created_at,user_id"), ("order", "id.desc"), ("limit", str(limit))],
    )
    user_ids = sorted({log["user_id"] for log in logs if log.get("user_id")})
    users = get_users_by_ids(user_ids)
    for log in logs:
        user = users.get(log.get("user_id"), {})
        log["username"] = user.get("username")
        log["full_name"] = user.get("full_name")
    return logs


def get_setting(key: str) -> str | None:
    if key in _settings_cache:
        return _settings_cache[key]
    rows = client().select("settings", [("select", "value"), ("key", f"eq.{key}"), ("limit", "1")])
    value = rows[0].get("value") if rows else None
    _settings_cache[key] = value
    return value


def set_setting(key: str, value: str) -> None:
    rows = client().select("settings", [("select", "id"), ("key", f"eq.{key}"), ("limit", "1")])
    if rows:
        client().update("settings", {"value": value, "updated_at": now_iso()}, [("key", f"eq.{key}")])
    else:
        client().insert("settings", {"key": key, "value": value})
    _settings_cache[key] = value


def clear_session() -> None:
    client().delete("settings", [("key", "eq.session_user_id")])
    _settings_cache.pop("session_user_id", None)


def get_users_by_ids(user_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not user_ids:
        return {}
    ids = ",".join(str(user_id) for user_id in user_ids)
    rows = client().select("users", [("select", "id,username,full_name"), ("id", f"in.({ids})")])
    return {int(row["id"]): row for row in rows}


def get_product_barcodes(product_id: int) -> list[str]:
    rows = client().select(
        "product_barcodes",
        [("select", "barcode"), ("product_id", f"eq.{product_id}"), ("order", "is_primary.desc,id.asc")],
    )
    return [str(row["barcode"]) for row in rows]


def product_to_app(product: dict[str, Any], matched_barcode: str | None = None) -> dict[str, Any]:
    barcodes = get_product_barcodes(int(product["id"]))
    primary = barcodes[0] if barcodes else (product.get("barcode") or "")
    result = dict(product)
    result["barcodes"] = barcodes
    result["primary_barcode"] = primary
    result["barcode"] = matched_barcode or primary
    return result


def products_to_app(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not products:
        return []

    product_ids = [int(product["id"]) for product in products]
    ids = ",".join(str(product_id) for product_id in product_ids)
    barcode_rows = client().select(
        "product_barcodes",
        [("select", "product_id,barcode"), ("product_id", f"in.({ids})"), ("order", "is_primary.desc,id.asc")],
    )
    barcodes_by_product: dict[int, list[str]] = {product_id: [] for product_id in product_ids}
    for row in barcode_rows:
        barcodes_by_product.setdefault(int(row["product_id"]), []).append(str(row["barcode"]))

    app_products = []
    for product in products:
        barcodes = barcodes_by_product.get(int(product["id"]), [])
        primary = barcodes[0] if barcodes else (product.get("barcode") or "")
        result = dict(product)
        result["barcodes"] = barcodes
        result["primary_barcode"] = primary
        result["barcode"] = primary
        app_products.append(result)
    return app_products


def get_all_products(limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    init_db()
    query = [
        ("select", "id,barcode,name,price,category,stock_qty,requires_weight,image_path"),
        ("active", "eq.true"),
        ("order", "id.desc"),
    ]
    if limit is not None:
        query.extend([("limit", str(limit)), ("offset", str(offset))])
    return products_to_app(client().select("products", query))


def search_products(keyword: str, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    init_db()
    clean = keyword.strip().lower()
    if not clean:
        return get_all_products(limit, offset)
    products = get_all_products()
    matches = []
    for product in products:
        fields = [product.get("name"), product.get("barcode"), product.get("primary_barcode"), product.get("category")]
        fields.extend(product.get("barcodes") or [])
        if any(clean in str(value or "").lower() for value in fields):
            matches.append(product)
    matches.sort(key=lambda item: (str(item.get("name") or "").lower(), -int(item.get("id") or 0)))
    return matches[offset : offset + limit if limit is not None else None]


def count_products(keyword: str = "") -> int:
    return len(search_products(keyword)) if keyword.strip() else len(get_all_products())


def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    rows = client().select(
        "products",
        [("select", "id,barcode,name,price,category,stock_qty,requires_weight,image_path"), ("id", f"eq.{product_id}"), ("active", "eq.true"), ("limit", "1")],
    )
    return product_to_app(rows[0]) if rows else None


def get_product_by_barcode(barcode: str) -> dict[str, Any] | None:
    clean = barcode.strip()
    if not clean:
        return None
    rows = client().select(
        "products",
        [("select", "id,barcode,name,price,category,stock_qty,requires_weight,image_path"), ("barcode", f"eq.{clean}"), ("active", "eq.true"), ("limit", "1")],
    )
    if rows:
        return product_to_app(rows[0], clean)
    barcode_rows = client().select("product_barcodes", [("select", "product_id"), ("barcode", f"eq.{clean}"), ("limit", "1")])
    if not barcode_rows:
        return None
    product = get_product_by_id(int(barcode_rows[0]["product_id"]))
    if product:
        product["barcode"] = clean
    return product


def barcode_exists(barcode: str, exclude_product_id: int | None = None) -> bool:
    product = get_product_by_barcode(barcode)
    if product is None:
        return False
    return exclude_product_id is None or int(product["id"]) != int(exclude_product_id)


def add_product(
    name: str,
    price: float,
    category: str,
    stock_qty: float,
    requires_weight: bool,
    image_path: str,
    barcodes: list[str],
) -> int:
    normalized = [barcode.strip() for barcode in barcodes if barcode.strip()]
    primary = normalized[0] if normalized else None
    rows = client().insert(
        "products",
        {
            "barcode": primary,
            "name": name.strip(),
            "price": price,
            "category": category.strip(),
            "stock_qty": stock_qty,
            "requires_weight": requires_weight,
            "image_path": image_path.strip() or None,
        },
    )
    product_id = int(rows[0]["id"])
    if normalized:
        client().insert(
            "product_barcodes",
            [{"product_id": product_id, "barcode": value, "is_primary": index == 0} for index, value in enumerate(normalized)],
        )
    return product_id


def update_product(
    product_id: int,
    name: str,
    price: float,
    category: str,
    stock_qty: float,
    requires_weight: bool,
    image_path: str,
    barcodes: list[str],
) -> None:
    normalized = [barcode.strip() for barcode in barcodes if barcode.strip()]
    primary = normalized[0] if normalized else None
    api = client()
    api.update(
        "products",
        {
            "barcode": primary,
            "name": name.strip(),
            "price": price,
            "category": category.strip(),
            "stock_qty": stock_qty,
            "requires_weight": requires_weight,
            "image_path": image_path.strip() or None,
            "updated_at": now_iso(),
        },
        [("id", f"eq.{product_id}")],
    )
    api.delete("product_barcodes", [("product_id", f"eq.{product_id}")])
    if normalized:
        api.insert(
            "product_barcodes",
            [{"product_id": product_id, "barcode": value, "is_primary": index == 0} for index, value in enumerate(normalized)],
        )


def delete_product(product_id: int) -> None:
    client().update("products", {"active": False, "updated_at": now_iso()}, [("id", f"eq.{product_id}")])


def get_available_stock(product_id: int) -> float:
    product = get_product_by_id(product_id)
    return float(product.get("stock_qty") or 0) if product else 0.0


def is_barcode_available(barcode: str) -> bool:
    return get_product_by_barcode(barcode) is not None


def was_barcode_sold(barcode: str) -> bool:
    rows = client().select("sale_items", [("select", "sale_id"), ("barcode", f"eq.{barcode.strip()}")])
    if not rows:
        return False
    sale_ids = ",".join(str(row["sale_id"]) for row in rows)
    sales = client().select("sales", [("select", "id"), ("id", f"in.({sale_ids})"), ("status", "eq.completed"), ("limit", "1")])
    return bool(sales)


def find_product_for_sale(keyword: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    clean = keyword.strip()
    if not clean:
        return None, []
    barcode_match = get_product_by_barcode(clean)
    if barcode_match:
        return barcode_match, [barcode_match]
    matches = search_products(clean)
    exact = [product for product in matches if str(product["name"]).lower() == clean.lower()]
    if len(exact) == 1:
        return exact[0], exact
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def create_sale(
    total_amount: float,
    payment_method: str,
    sale_items: list[dict[str, Any]],
    user_id: int | None = None,
    register_id: int | None = None,
    shift_id: int | None = None,
    tendered_amount: float = 0,
    change_amount: float = 0,
    note: str = "",
    payments: list[dict[str, Any]] | None = None,
) -> int:
    api = client()
    for item in sale_items:
        product_id = item.get("product_id")
        if product_id is not None:
            available = get_available_stock(int(product_id))
            if float(item.get("qty") or 0) > available:
                raise ValueError(f"Insufficient stock for product #{product_id}: requested {item.get('qty')}, available {available:g}.")

    sale_rows = api.insert(
        "sales",
        {
            "user_id": user_id,
            "register_id": register_id,
            "shift_id": shift_id,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "tendered_amount": tendered_amount,
            "change_amount": change_amount,
            "note": note.strip(),
            "status": "completed",
        },
    )
    sale_id = int(sale_rows[0]["id"])
    api.insert(
        "sale_items",
        [
            {
                "sale_id": sale_id,
                "product_id": item.get("product_id"),
                "barcode": item.get("barcode"),
                "name": item.get("name", ""),
                "qty": item["qty"],
                "price": item["price"],
                "subtotal": item["subtotal"],
            }
            for item in sale_items
        ],
    )
    for item in sale_items:
        product_id = item.get("product_id")
        if product_id is None:
            continue
        current = get_available_stock(int(product_id))
        api.update(
            "products",
            {"stock_qty": max(current - float(item.get("qty") or 0), 0), "updated_at": now_iso()},
            [("id", f"eq.{product_id}")],
        )
    payment_rows = payments or [{"method": payment_method, "amount": total_amount}]
    api.insert("sale_payments", [{"sale_id": sale_id, "method": payment["method"], "amount": payment["amount"]} for payment in payment_rows])
    api.insert("sync_queue", {"entity_type": "sale", "entity_id": sale_id, "operation": "create", "payload": f"sale_id={sale_id};total={total_amount:.2f}"})
    return sale_id


def void_sale(sale_id: int) -> None:
    api = client()
    api.update("sales", {"status": "voided"}, [("id", f"eq.{sale_id}")])
    api.insert("sync_queue", {"entity_type": "sale", "entity_id": sale_id, "operation": "void", "payload": f"sale_id={sale_id}"})


def sales_between(start_date: str, end_date: str, status: str = "completed") -> list[dict[str, Any]]:
    return client().select(
        "sales",
        [
            ("select", "id,user_id,register_id,shift_id,total_amount,payment_method,tendered_amount,change_amount,status,created_at"),
            ("created_at", f"gte.{start_date}"),
            ("created_at", f"lte.{end_date}"),
            ("status", f"eq.{status}"),
            ("order", "id.desc"),
        ],
    )


def today_summary() -> dict[str, float | int]:
    today = datetime.now().strftime("%Y-%m-%d")
    sales = sales_between(today, f"{today} 23:59:59")
    sale_ids = [int(sale["id"]) for sale in sales]
    items = sale_items_for_sales(sale_ids)
    total = sum(float(sale.get("total_amount") or 0) for sale in sales)
    count = len(sales)
    return {
        "sales_count": count,
        "sales_total": total,
        "items_sold": sum(float(item.get("qty") or 0) for item in items),
        "average_sale": total / count if count else 0,
    }


def sale_items_for_sales(sale_ids: list[int]) -> list[dict[str, Any]]:
    if not sale_ids:
        return []
    ids = ",".join(str(sale_id) for sale_id in sale_ids)
    return client().select("sale_items", [("select", "id,sale_id,product_id,barcode,name,qty,price,subtotal"), ("sale_id", f"in.({ids})")])


def sales_report(start_date: str, end_date: str, status: str = "completed") -> list[dict[str, Any]]:
    sales = sales_between(start_date, end_date, status)
    users = get_users_by_ids([int(sale["user_id"]) for sale in sales if sale.get("user_id")])
    for sale in sales:
        sale["cashier_name"] = users.get(sale.get("user_id"), {}).get("username")
    return sales


def sales_by_cashier(start_date: str, end_date: str) -> list[dict[str, Any]]:
    sales = sales_between(start_date, end_date)
    users = get_users_by_ids([int(sale["user_id"]) for sale in sales if sale.get("user_id")])
    grouped: dict[int | None, dict[str, Any]] = {}
    for sale in sales:
        user_id = sale.get("user_id")
        row = grouped.setdefault(user_id, {"cashier_name": users.get(user_id, {}).get("username"), "transaction_count": 0, "total_sales": 0.0})
        row["transaction_count"] += 1
        row["total_sales"] += float(sale.get("total_amount") or 0)
    return sorted(grouped.values(), key=lambda row: row["total_sales"], reverse=True)


def sales_by_payment(start_date: str, end_date: str) -> list[dict[str, Any]]:
    sales = sales_between(start_date, end_date)
    grouped: dict[str, dict[str, Any]] = {}
    for sale in sales:
        method = sale.get("payment_method") or "Unknown"
        row = grouped.setdefault(method, {"payment_method": method, "transaction_count": 0, "total_sales": 0.0})
        row["transaction_count"] += 1
        row["total_sales"] += float(sale.get("total_amount") or 0)
    return sorted(grouped.values(), key=lambda row: row["total_sales"], reverse=True)


def sales_by_product(start_date: str, end_date: str, limit: int = 50) -> list[dict[str, Any]]:
    sale_ids = [int(sale["id"]) for sale in sales_between(start_date, end_date)]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in sale_items_for_sales(sale_ids):
        key = (item.get("barcode") or "", item.get("name") or "")
        row = grouped.setdefault(key, {"barcode": key[0], "name": key[1], "quantity_sold": 0.0, "total_sales": 0.0})
        row["quantity_sold"] += float(item.get("qty") or 0)
        row["total_sales"] += float(item.get("subtotal") or 0)
    return sorted(grouped.values(), key=lambda row: row["total_sales"], reverse=True)[:limit]


def shift_summary(start_date: str, end_date: str) -> list[dict[str, Any]]:
    shifts = client().select(
        "cash_shifts",
        [
            ("select", "id,register_id,user_id,opened_at,closed_at,opening_balance,expected_balance,closing_balance,status"),
            ("opened_at", f"gte.{start_date}"),
            ("opened_at", f"lte.{end_date}"),
            ("order", "id.desc"),
        ],
    )
    users = get_users_by_ids([int(shift["user_id"]) for shift in shifts if shift.get("user_id")])
    register_ids = sorted({int(shift["register_id"]) for shift in shifts if shift.get("register_id")})
    registers = {}
    if register_ids:
        ids = ",".join(str(register_id) for register_id in register_ids)
        registers = {int(row["id"]): row for row in client().select("registers", [("select", "id,name"), ("id", f"in.({ids})")])}
    for shift in shifts:
        shift["register_name"] = registers.get(shift.get("register_id"), {}).get("name")
        shift["cashier_name"] = users.get(shift.get("user_id"), {}).get("username")
    return shifts


def dashboard_summary(start_date: str, end_date: str) -> dict[str, Any]:
    sales = sales_between(start_date, end_date)
    sale_ids = [int(sale["id"]) for sale in sales]
    items = sale_items_for_sales(sale_ids)
    payment_breakdown = sales_by_payment(start_date, end_date)
    today = today_summary()
    return {
        "count": len(sales),
        "total": sum(float(sale.get("total_amount") or 0) for sale in sales),
        "items_sold": sum(float(item.get("qty") or 0) for item in items),
        "payment_breakdown": [
            {"method": row["payment_method"], "count": row["transaction_count"], "total": row["total_sales"]}
            for row in payment_breakdown
        ],
        "today_count": today["sales_count"],
        "today_total": today["sales_total"],
    }


def top_products(start_date: str, end_date: str, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "barcode": row["barcode"],
            "name": row["name"] or row["barcode"] or "Unknown Product",
            "total_qty": row["quantity_sold"],
            "total_sales": row["total_sales"],
        }
        for row in sales_by_product(start_date, end_date, limit)
    ]


def sync_insert_product(payload: dict[str, Any]) -> None:
    api = client()
    product = dict(payload["product"])
    barcodes = list(payload.get("barcodes") or [])
    api.insert("products", product)
    if barcodes:
        api.insert(
            "product_barcodes",
            [
                {
                    "product_id": product["id"],
                    "barcode": barcode,
                    "is_primary": index == 0,
                }
                for index, barcode in enumerate(barcodes)
            ],
        )


def sync_create_sale(payload: dict[str, Any]) -> None:
    api = client()
    sale = dict(payload["sale"])
    sale_items = list(payload.get("sale_items") or [])
    payments = list(payload.get("payments") or [])
    sale_id = int(sale["id"])
    if api.select("sales", [("select", "id"), ("id", f"eq.{sale_id}"), ("limit", "1")]):
        return
    api.insert("sales", sale)
    if sale_items:
        api.insert("sale_items", sale_items)
    if payments:
        api.insert("sale_payments", payments)
    for item in sale_items:
        product_id = item.get("product_id")
        if product_id is None:
            continue
        product = get_product_by_id(int(product_id))
        if product is None:
            continue
        current = float(product.get("stock_qty") or 0)
        api.update(
            "products",
            {"stock_qty": max(current - float(item.get("qty") or 0), 0), "updated_at": now_iso()},
            [("id", f"eq.{product_id}")],
        )


def replay_offline_operation(row: sqlite3.Row) -> None:
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = legacy_payload_to_json(row)
    entity_type = row["entity_type"]
    operation = row["operation"]
    entity_id = row["entity_id"]

    if entity_type == "product" and operation == "create":
        sync_insert_product(payload)
    elif entity_type == "product" and operation == "update":
        update_product(int(entity_id), **payload)
    elif entity_type == "product" and operation == "delete":
        delete_product(int(entity_id))
    elif entity_type == "sale" and operation == "create":
        sync_create_sale(payload)
    elif entity_type == "sale" and operation == "void":
        void_sale(int(entity_id))
    else:
        raise SupabaseError(f"Unsupported offline operation: {entity_type}/{operation}")


def legacy_payload_to_json(row: sqlite3.Row) -> dict[str, Any]:
    if row["entity_type"] == "sale" and row["operation"] == "create":
        raw_payload = str(row["payload"] or "")
        sale_id_text = raw_payload.split(";", 1)[0].replace("sale_id=", "").strip()
        if sale_id_text.isdigit():
            return local_sale_payload(int(sale_id_text))
    if row["entity_type"] == "sale" and row["operation"] == "void" and row["entity_id"] is not None:
        return {}
    raise ValueError(f"Cannot replay legacy sync payload for row #{row['id']}")


def local_sale_payload(sale_id: int) -> dict[str, Any]:
    with local_connection() as connection:
        sale = connection.execute(
            """
            SELECT id, user_id, register_id, shift_id, total_amount, payment_method,
                   tendered_amount, change_amount, note, status, created_at
            FROM sales
            WHERE id = ?
            """,
            (sale_id,),
        ).fetchone()
        if sale is None:
            raise ValueError(f"Local sale #{sale_id} no longer exists.")

        items = connection.execute(
            """
            SELECT sale_id, product_id, barcode, name, qty, price, subtotal
            FROM sale_items
            WHERE sale_id = ?
            """,
            (sale_id,),
        ).fetchall()
        payments = connection.execute(
            """
            SELECT sale_id, method, amount
            FROM sale_payments
            WHERE sale_id = ?
            """,
            (sale_id,),
        ).fetchall()

    return {
        "sale": {key: sale[key] for key in sale.keys()},
        "sale_items": [{key: item[key] for key in item.keys()} for item in items],
        "payments": [{key: payment[key] for key in payment.keys()} for payment in payments],
    }


def flush_sync_queue(limit: int = 5) -> int:
    ensure_local_sync_queue()
    if not can_connect():
        return 0

    synced = 0
    with local_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, entity_type, entity_id, operation, payload
            FROM sync_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        for row in rows:
            try:
                replay_offline_operation(row)
            except (SupabaseError, ValueError, json.JSONDecodeError) as error:
                connection.execute(
                    """
                    UPDATE sync_queue
                    SET retry_count = retry_count + 1,
                        last_error = ?
                    WHERE id = ?
                    """,
                    (str(error), row["id"]),
                )
                connection.commit()
                break

            connection.execute(
                """
                UPDATE sync_queue
                SET status = 'synced', synced_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = ?
                """,
                (row["id"],),
            )
            connection.commit()
            synced += 1

    return synced
