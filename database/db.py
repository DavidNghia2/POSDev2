import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parents[1] / "pos.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    cursor = connection.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cursor.fetchall())


def add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not column_exists(connection, table_name, column_name):
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                sku TEXT UNIQUE,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                stock_qty REAL DEFAULT 0,
                requires_weight BOOLEAN DEFAULT 0,
                active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                register_id INTEGER,
                shift_id INTEGER,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                tendered_amount REAL DEFAULT 0,
                change_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER,
                barcode TEXT,
                name TEXT,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sale_id) REFERENCES sales (id)
            )
            """
        )
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
        add_column_if_missing(connection, "products", "sku", "sku TEXT")
        add_column_if_missing(connection, "products", "stock_qty", "stock_qty REAL DEFAULT 0")
        add_column_if_missing(connection, "products", "active", "active INTEGER DEFAULT 1")
        add_column_if_missing(connection, "products", "updated_at", "updated_at TEXT")
        add_column_if_missing(connection, "sales", "user_id", "user_id INTEGER")
        add_column_if_missing(connection, "sales", "register_id", "register_id INTEGER")
        add_column_if_missing(connection, "sales", "shift_id", "shift_id INTEGER")
        add_column_if_missing(connection, "sales", "tendered_amount", "tendered_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "change_amount", "change_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "status", "status TEXT DEFAULT 'completed'")
        add_column_if_missing(connection, "sale_items", "product_id", "product_id INTEGER")
        add_column_if_missing(connection, "sale_items", "name", "name TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products (sku)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales (created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_user ON sales (user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_register ON sales (register_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_shift ON sales (shift_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items (sale_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue (status)")
        connection.commit()


def normalize_barcode(barcode: str) -> str | None:
    clean_barcode = barcode.strip()
    return clean_barcode or None


def get_all_products() -> list[sqlite3.Row]:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, barcode, name, price, category, requires_weight
            FROM products
            WHERE active = 1
            ORDER BY id DESC
            """
        )
        return cursor.fetchall()


def search_products(keyword: str) -> list[sqlite3.Row]:
    init_db()
    clean_keyword = keyword.strip()
    if not clean_keyword:
        return get_all_products()

    search_value = f"%{clean_keyword}%"
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, barcode, name, price, category, requires_weight
            FROM products
            WHERE active = 1 AND (name LIKE ? OR barcode LIKE ? OR sku LIKE ?)
            ORDER BY name ASC, id DESC
            """,
            (search_value, search_value, search_value),
        )
        return cursor.fetchall()


def get_product_by_barcode(barcode: str) -> sqlite3.Row | None:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return None

    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, barcode, name, price, category, requires_weight
            FROM products
            WHERE active = 1 AND barcode = ?
            LIMIT 1
            """,
            (clean_barcode,),
        )
        return cursor.fetchone()


def add_product(
    barcode: str,
    name: str,
    price: float,
    category: str,
    requires_weight: bool,
) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO products (barcode, name, price, category, requires_weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalize_barcode(barcode),
                name.strip(),
                price,
                category.strip(),
                int(requires_weight),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def update_product(
    product_id: int,
    barcode: str,
    name: str,
    price: float,
    category: str,
    requires_weight: bool,
) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET barcode = ?, name = ?, price = ?, category = ?, requires_weight = ?
            WHERE id = ?
            """,
            (
                normalize_barcode(barcode),
                name.strip(),
                price,
                category.strip(),
                int(requires_weight),
                product_id,
            ),
        )
        connection.commit()


def delete_product(product_id: int) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute("UPDATE products SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (product_id,))
        connection.commit()


def find_product_for_sale(keyword: str) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    clean_keyword = keyword.strip()
    if not clean_keyword:
        return None, []

    barcode_match = get_product_by_barcode(clean_keyword)
    if barcode_match is not None:
        return barcode_match, [barcode_match]

    matches = search_products(clean_keyword)
    exact_name_matches = [
        product for product in matches if str(product["name"]).lower() == clean_keyword.lower()
    ]
    if len(exact_name_matches) == 1:
        return exact_name_matches[0], exact_name_matches

    if len(matches) == 1:
        return matches[0], matches

    return None, matches


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def create_sale(
    total_amount: float,
    payment_method: str,
    sale_items: list[dict[str, Any]],
    user_id: int | None = None,
    register_id: int | None = None,
    shift_id: int | None = None,
    tendered_amount: float = 0,
    change_amount: float = 0,
    payments: list[dict[str, Any]] | None = None,
) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO sales (
                user_id, register_id, shift_id, total_amount, payment_method,
                tendered_amount, change_amount, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
            """,
            (
                user_id,
                register_id,
                shift_id,
                total_amount,
                payment_method,
                tendered_amount,
                change_amount,
            ),
        )
        sale_id = int(cursor.lastrowid)

        connection.executemany(
            """
            INSERT INTO sale_items (sale_id, product_id, barcode, name, qty, price, subtotal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    sale_id,
                    item.get("product_id"),
                    item["barcode"],
                    item.get("name", ""),
                    item["qty"],
                    item["price"],
                    item["subtotal"],
                )
                for item in sale_items
            ],
        )
        payment_rows = payments or [{"method": payment_method, "amount": total_amount}]
        connection.executemany(
            """
            INSERT INTO sale_payments (sale_id, method, amount)
            VALUES (?, ?, ?)
            """,
            [(sale_id, payment["method"], payment["amount"]) for payment in payment_rows],
        )
        connection.execute(
            """
            INSERT INTO sync_queue (entity_type, entity_id, operation, payload)
            VALUES ('sale', ?, 'create', ?)
            """,
            (sale_id, f"sale_id={sale_id};total={total_amount:.2f}"),
        )
        connection.commit()
        return sale_id


def void_sale(sale_id: int) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            "UPDATE sales SET status = 'voided' WHERE id = ?",
            (sale_id,),
        )
        connection.execute(
            """
            INSERT INTO sync_queue (entity_type, entity_id, operation, payload)
            VALUES ('sale', ?, 'void', ?)
            """,
            (sale_id, f"sale_id={sale_id}"),
        )
        connection.commit()
