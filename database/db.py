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
            CREATE TABLE IF NOT EXISTS product_barcodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                barcode TEXT NOT NULL UNIQUE,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
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
        add_column_if_missing(connection, "products", "image_path", "image_path TEXT")
        add_column_if_missing(connection, "sales", "user_id", "user_id INTEGER")
        add_column_if_missing(connection, "sales", "register_id", "register_id INTEGER")
        add_column_if_missing(connection, "sales", "shift_id", "shift_id INTEGER")
        add_column_if_missing(connection, "sales", "tendered_amount", "tendered_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "change_amount", "change_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "status", "status TEXT DEFAULT 'completed'")
        add_column_if_missing(connection, "sale_items", "product_id", "product_id INTEGER")
        add_column_if_missing(connection, "sale_items", "name", "name TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_product_barcodes_product ON product_barcodes (product_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_product_barcodes_barcode ON product_barcodes (barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products (sku)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales (created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_user ON sales (user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_register ON sales (register_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_shift ON sales (shift_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items (sale_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue (status)")
        connection.execute(
            """
            INSERT OR IGNORE INTO product_barcodes (product_id, barcode, is_primary)
            SELECT id, barcode, 1
            FROM products
            WHERE barcode IS NOT NULL AND TRIM(barcode) <> ''
            """
        )
        connection.commit()


def normalize_barcode(barcode: str) -> str | None:
    clean_barcode = barcode.strip()
    return clean_barcode or None


def normalize_barcodes(barcodes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for barcode in barcodes:
        clean_barcode = barcode.strip()
        if not clean_barcode or clean_barcode in seen:
            continue
        normalized.append(clean_barcode)
        seen.add(clean_barcode)
    return normalized


def fetch_product_barcodes(connection: sqlite3.Connection, product_id: int) -> list[str]:
    rows = connection.execute(
        """
        SELECT barcode
        FROM product_barcodes
        WHERE product_id = ?
        ORDER BY is_primary DESC, id ASC
        """,
        (product_id,),
    ).fetchall()
    return [str(row["barcode"]) for row in rows]


def get_available_stock(product_id: int) -> float:
    """Return sellable stock using explicit stock when present, otherwise remaining barcodes."""
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT stock_qty
            FROM products
            WHERE active = 1 AND id = ?
            LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            return 0.0

        stock_qty = float(row["stock_qty"] or 0)
        if stock_qty > 0:
            return stock_qty

        barcode_row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM product_barcodes
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()
        return float(barcode_row["count"] if barcode_row else 0)


def is_barcode_available(barcode: str) -> bool:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return False

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND (p.barcode = ? OR pb.barcode = ?)
            LIMIT 1
            """,
            (clean_barcode, clean_barcode),
        ).fetchone()
        return row is not None


def was_barcode_sold(barcode: str) -> bool:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return False

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE si.barcode = ? AND s.status = 'completed'
            LIMIT 1
            """,
            (clean_barcode,),
        ).fetchone()
        return row is not None


def remove_sold_barcodes(connection: sqlite3.Connection, sale_items: list[dict[str, Any]]) -> None:
    """Remove scanned barcodes after a completed sale and keep primary barcode in sync."""
    affected_product_ids: set[int] = set()

    for item in sale_items:
        barcode = normalize_barcode(str(item.get("barcode") or ""))
        if barcode is None:
            continue

        product_id = item.get("product_id")
        if product_id is None:
            row = connection.execute(
                """
                SELECT p.id
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND (p.barcode = ? OR pb.barcode = ?)
                LIMIT 1
                """,
                (barcode, barcode),
            ).fetchone()
            if row is None:
                continue
            product_id = int(row["id"])
        else:
            product_id = int(product_id)

        connection.execute(
            "DELETE FROM product_barcodes WHERE product_id = ? AND barcode = ?",
            (product_id, barcode),
        )
        connection.execute(
            """
            UPDATE products
            SET barcode = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND barcode = ?
            """,
            (product_id, barcode),
        )
        affected_product_ids.add(product_id)

    for product_id in affected_product_ids:
        remaining_barcodes = fetch_product_barcodes(connection, product_id)
        next_primary = remaining_barcodes[0] if remaining_barcodes else None
        connection.execute(
            """
            UPDATE products
            SET barcode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_primary, product_id),
        )
        connection.execute(
            "UPDATE product_barcodes SET is_primary = 0 WHERE product_id = ?",
            (product_id,),
        )
        if next_primary is not None:
            connection.execute(
                """
                UPDATE product_barcodes
                SET is_primary = 1
                WHERE product_id = ? AND barcode = ?
                """,
                (product_id, next_primary),
            )


def get_available_stock_with_connection(connection: sqlite3.Connection, product_id: int) -> float:
    row = connection.execute(
        """
        SELECT stock_qty
        FROM products
        WHERE active = 1 AND id = ?
        LIMIT 1
        """,
        (product_id,),
    ).fetchone()
    if row is None:
        return 0.0

    stock_qty = float(row["stock_qty"] or 0)
    if stock_qty > 0:
        return stock_qty

    barcode_row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM product_barcodes
        WHERE product_id = ?
        """,
        (product_id,),
    ).fetchone()
    return float(barcode_row["count"] if barcode_row else 0)


def ensure_sale_items_available(connection: sqlite3.Connection, sale_items: list[dict[str, Any]]) -> None:
    requested_by_product: dict[int, float] = {}

    for item in sale_items:
        product_id = item.get("product_id")
        barcode = normalize_barcode(str(item.get("barcode") or ""))

        if barcode is not None:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND (p.barcode = ? OR pb.barcode = ?)
                LIMIT 1
                """,
                (barcode, barcode),
            ).fetchone()
            if row is None:
                raise ValueError(f"Barcode {barcode} is no longer available in inventory.")

        if product_id is None:
            continue

        requested_by_product[int(product_id)] = requested_by_product.get(int(product_id), 0.0) + float(
            item.get("qty") or 0
        )

    for product_id, requested_qty in requested_by_product.items():
        available_qty = get_available_stock_with_connection(connection, product_id)
        if requested_qty > available_qty:
            raise ValueError(
                f"Insufficient stock for product #{product_id}: requested {requested_qty:g}, available {available_qty:g}."
            )


def reduce_explicit_stock(connection: sqlite3.Connection, sale_items: list[dict[str, Any]]) -> None:
    sold_by_product: dict[int, float] = {}
    for item in sale_items:
        product_id = item.get("product_id")
        if product_id is None:
            continue
        sold_by_product[int(product_id)] = sold_by_product.get(int(product_id), 0.0) + float(item.get("qty") or 0)

    for product_id, sold_qty in sold_by_product.items():
        connection.execute(
            """
            UPDATE products
            SET stock_qty = CASE
                WHEN COALESCE(stock_qty, 0) > 0 THEN MAX(COALESCE(stock_qty, 0) - ?, 0)
                ELSE stock_qty
            END,
            updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (sold_qty, product_id),
        )


def product_row_to_dict(
    row: sqlite3.Row,
    barcodes: list[str] | None = None,
    matched_barcode: str | None = None,
) -> dict[str, Any]:
    product = row_to_dict(row)
    product_barcodes = barcodes or []
    primary_barcode = product_barcodes[0] if product_barcodes else (product.get("barcode") or "")
    product["barcodes"] = product_barcodes
    product["primary_barcode"] = primary_barcode
    product["barcode"] = matched_barcode or primary_barcode
    return product


def get_all_products() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, barcode, name, price, category, stock_qty, requires_weight, image_path
            FROM products
            WHERE active = 1
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
        return [
            product_row_to_dict(row, fetch_product_barcodes(connection, int(row["id"])))
            for row in rows
        ]


def search_products(keyword: str) -> list[dict[str, Any]]:
    init_db()
    clean_keyword = keyword.strip()
    if not clean_keyword:
        return get_all_products()

    search_value = f"%{clean_keyword}%"
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT DISTINCT p.id, p.barcode, p.name, p.price, p.category, p.stock_qty, p.requires_weight, p.image_path
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1
              AND (p.name LIKE ? OR p.barcode LIKE ? OR p.sku LIKE ? OR pb.barcode LIKE ?)
            ORDER BY p.name ASC, p.id DESC
            """,
            (search_value, search_value, search_value, search_value),
        )
        rows = cursor.fetchall()
        return [
            product_row_to_dict(row, fetch_product_barcodes(connection, int(row["id"])))
            for row in rows
        ]


def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, barcode, name, price, category, stock_qty, requires_weight, image_path
            FROM products
            WHERE active = 1 AND id = ?
            LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            return None
        return product_row_to_dict(row, fetch_product_barcodes(connection, int(row["id"])))


def get_product_by_barcode(barcode: str) -> dict[str, Any] | None:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return None

    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT p.id, p.barcode, p.name, p.price, p.category, p.stock_qty, p.requires_weight, p.image_path
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND (p.barcode = ? OR pb.barcode = ?)
            LIMIT 1
            """,
            (clean_barcode, clean_barcode),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return product_row_to_dict(
            row,
            fetch_product_barcodes(connection, int(row["id"])),
            matched_barcode=clean_barcode,
        )


def barcode_exists(barcode: str, exclude_product_id: int | None = None) -> bool:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return False

    with get_connection() as connection:
        if exclude_product_id is None:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND (p.barcode = ? OR pb.barcode = ?)
                LIMIT 1
                """,
                (clean_barcode, clean_barcode),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1
                  AND p.id <> ?
                  AND (p.barcode = ? OR pb.barcode = ?)
                LIMIT 1
                """,
                (exclude_product_id, clean_barcode, clean_barcode),
            ).fetchone()
        return row is not None


def add_product(
    name: str,
    price: float,
    category: str,
    requires_weight: bool,
    image_path: str,
    barcodes: list[str],
) -> int:
    init_db()
    normalized_barcodes = normalize_barcodes(barcodes)
    primary_barcode = normalized_barcodes[0] if normalized_barcodes else None
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO products (barcode, name, price, category, requires_weight, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                int(requires_weight),
                image_path.strip() or None,
            ),
        )
        product_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO product_barcodes (product_id, barcode, is_primary)
            VALUES (?, ?, ?)
            """,
            [
                (product_id, barcode_value, int(index == 0))
                for index, barcode_value in enumerate(normalized_barcodes)
            ],
        )
        connection.commit()
        return product_id


def update_product(
    product_id: int,
    name: str,
    price: float,
    category: str,
    requires_weight: bool,
    image_path: str,
    barcodes: list[str],
) -> None:
    init_db()
    normalized_barcodes = normalize_barcodes(barcodes)
    primary_barcode = normalized_barcodes[0] if normalized_barcodes else None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET barcode = ?, name = ?, price = ?, category = ?, requires_weight = ?,
                image_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                int(requires_weight),
                image_path.strip() or None,
                product_id,
            ),
        )
        connection.execute("DELETE FROM product_barcodes WHERE product_id = ?", (product_id,))
        connection.executemany(
            """
            INSERT INTO product_barcodes (product_id, barcode, is_primary)
            VALUES (?, ?, ?)
            """,
            [
                (product_id, barcode_value, int(index == 0))
                for index, barcode_value in enumerate(normalized_barcodes)
            ],
        )
        connection.commit()


def delete_product(product_id: int) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute("UPDATE products SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (product_id,))
        connection.commit()


def find_product_for_sale(keyword: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
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
        ensure_sale_items_available(connection, sale_items)
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
        remove_sold_barcodes(connection, sale_items)
        reduce_explicit_stock(connection, sale_items)
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
