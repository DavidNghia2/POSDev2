import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app_paths import database_path
from cloud import inventory as cloud_inventory
from cloud import products as cloud_products

DB_PATH = database_path()
DEFAULT_LOCAL_STORE_ID = "local-default-store"


def _truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def get_current_store_id() -> str:
    try:
        from login import get_current_store_id as auth_current_store_id

        store_id = auth_current_store_id()
        return store_id or DEFAULT_LOCAL_STORE_ID
    except Exception:
        return DEFAULT_LOCAL_STORE_ID


def current_store_id_from_connection(connection: sqlite3.Connection) -> str:
    try:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = 'current_store_id' LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return DEFAULT_LOCAL_STORE_ID
    if row is not None and str(row["value"] or "").strip():
        return str(row["value"])
    return DEFAULT_LOCAL_STORE_ID


def cloud_sync_enabled_for_store(store_id: str) -> bool:
    return store_id != DEFAULT_LOCAL_STORE_ID and cloud_products.cloud_products_available()


def should_seed_demo_catalog(connection: sqlite3.Connection) -> bool:
    seed_flag = os.getenv("ENABLE_DEMO_SEED", "").strip()
    if seed_flag:
        return _truthy_env(seed_flag)
    store_id = current_store_id_from_connection(connection)
    return store_id == DEFAULT_LOCAL_STORE_ID and not cloud_products.cloud_products_available()


def scoped_meta_key(key: str, store_id: str) -> str:
    return f"{store_id}:{key}"


def table_create_sql(connection: sqlite3.Connection, table_name: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return str(row["sql"] or "") if row is not None else ""


def rebuild_products_for_store_scoped_uniques(connection: sqlite3.Connection) -> bool:
    create_sql = table_create_sql(connection, "products").lower()
    if "barcode text unique" not in create_sql and "sku text unique" not in create_sql:
        return False

    connection.execute("DROP TABLE IF EXISTS products_store_scope_migration")
    connection.execute("ALTER TABLE products RENAME TO products_store_scope_migration")
    connection.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT,
            cloud_id TEXT,
            barcode TEXT,
            sku TEXT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            stock_qty REAL DEFAULT 0,
            requires_weight BOOLEAN DEFAULT 0,
            active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT,
            storage_path TEXT,
            image_url TEXT,
            sync_status TEXT DEFAULT 'local',
            last_synced_at TEXT,
            cloud_updated_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO products (
            id, store_id, cloud_id, barcode, sku, name, price, category, stock_qty,
            requires_weight, active, updated_at, image_path, storage_path, image_url,
            sync_status, last_synced_at, cloud_updated_at
        )
        SELECT
            id,
            COALESCE(NULLIF(TRIM(store_id), ''), ?),
            cloud_id,
            barcode,
            sku,
            name,
            price,
            category,
            COALESCE(stock_qty, 0),
            COALESCE(requires_weight, 0),
            COALESCE(active, 1),
            updated_at,
            image_path,
            NULL,
            NULL,
            COALESCE(sync_status, 'local'),
            last_synced_at,
            NULL
        FROM products_store_scope_migration
        """,
        (DEFAULT_LOCAL_STORE_ID,),
    )
    connection.execute("DROP TABLE products_store_scope_migration")
    return True


def rebuild_product_barcodes_for_store_scoped_uniques(
    connection: sqlite3.Connection,
    force: bool = False,
) -> bool:
    create_sql = table_create_sql(connection, "product_barcodes").lower()
    if not force and "barcode text not null unique" not in create_sql and "unique" not in create_sql:
        return False

    connection.execute("DROP TABLE IF EXISTS product_barcodes_store_scope_migration")
    connection.execute("ALTER TABLE product_barcodes RENAME TO product_barcodes_store_scope_migration")
    connection.execute(
        """
        CREATE TABLE product_barcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT,
            product_id INTEGER NOT NULL,
            barcode TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO product_barcodes (id, store_id, product_id, barcode, is_primary, created_at)
        SELECT
            id,
            COALESCE(NULLIF(TRIM(store_id), ''), ?),
            product_id,
            barcode,
            COALESCE(is_primary, 0),
            created_at
        FROM product_barcodes_store_scope_migration
        """,
        (DEFAULT_LOCAL_STORE_ID,),
    )
    connection.execute("DROP TABLE product_barcodes_store_scope_migration")
    return True


def rebuild_store_scoped_catalog_tables(connection: sqlite3.Connection) -> None:
    products_rebuilt = rebuild_products_for_store_scoped_uniques(connection)
    rebuild_product_barcodes_for_store_scoped_uniques(connection, force=products_rebuilt)


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT,
                cloud_id TEXT,
                barcode TEXT,
                sku TEXT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                stock_qty REAL DEFAULT 0,
                requires_weight BOOLEAN DEFAULT 0,
                active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                storage_path TEXT,
                image_url TEXT,
                sync_status TEXT DEFAULT 'local',
                last_synced_at TEXT,
                cloud_updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_barcodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT,
                product_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        add_column_if_missing(connection, "products", "sku", "sku TEXT")
        add_column_if_missing(connection, "products", "stock_qty", "stock_qty REAL DEFAULT 0")
        add_column_if_missing(connection, "products", "active", "active INTEGER DEFAULT 1")
        add_column_if_missing(connection, "products", "updated_at", "updated_at TEXT")
        add_column_if_missing(connection, "products", "image_path", "image_path TEXT")
        add_column_if_missing(connection, "products", "storage_path", "storage_path TEXT")
        add_column_if_missing(connection, "products", "image_url", "image_url TEXT")
        add_column_if_missing(connection, "products", "store_id", "store_id TEXT")
        add_column_if_missing(connection, "products", "cloud_id", "cloud_id TEXT")
        add_column_if_missing(connection, "products", "sync_status", "sync_status TEXT DEFAULT 'local'")
        add_column_if_missing(connection, "products", "last_synced_at", "last_synced_at TEXT")
        add_column_if_missing(connection, "products", "cloud_updated_at", "cloud_updated_at TEXT")
        add_column_if_missing(connection, "product_barcodes", "store_id", "store_id TEXT")
        rebuild_store_scoped_catalog_tables(connection)
        add_column_if_missing(connection, "sales", "user_id", "user_id INTEGER")
        add_column_if_missing(connection, "sales", "register_id", "register_id INTEGER")
        add_column_if_missing(connection, "sales", "shift_id", "shift_id INTEGER")
        add_column_if_missing(connection, "sales", "tendered_amount", "tendered_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "change_amount", "change_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "note", "note TEXT")
        add_column_if_missing(connection, "sales", "status", "status TEXT DEFAULT 'completed'")
        add_column_if_missing(connection, "sales", "store_id", "store_id TEXT")
        add_column_if_missing(connection, "sales", "cloud_id", "cloud_id TEXT")
        add_column_if_missing(connection, "sales", "client_uuid", "client_uuid TEXT")
        add_column_if_missing(connection, "sales", "sync_status", "sync_status TEXT DEFAULT 'local'")
        add_column_if_missing(connection, "sales", "sync_error", "sync_error TEXT")
        add_column_if_missing(connection, "sales", "last_synced_at", "last_synced_at TEXT")
        add_column_if_missing(connection, "sale_items", "product_id", "product_id INTEGER")
        add_column_if_missing(connection, "sale_items", "name", "name TEXT")
        add_column_if_missing(connection, "sale_items", "store_id", "store_id TEXT")
        add_column_if_missing(connection, "sale_payments", "store_id", "store_id TEXT")
        add_column_if_missing(connection, "sync_queue", "store_id", "store_id TEXT")
        store_id = current_store_id_from_connection(connection)
        for table_name in ("products", "product_barcodes", "sales", "sale_items", "sale_payments", "sync_queue"):
            connection.execute(
                f"UPDATE {table_name} SET store_id = ? WHERE store_id IS NULL OR TRIM(store_id) = ''",
                (store_id,),
            )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_store ON products (store_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_product_barcodes_store ON product_barcodes (store_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_product_barcodes_product ON product_barcodes (product_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_product_barcodes_barcode ON product_barcodes (barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products (sku)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_barcode_unique
            ON products (store_id, barcode)
            WHERE barcode IS NOT NULL AND TRIM(barcode) <> ''
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_sku_unique
            ON products (store_id, sku)
            WHERE sku IS NOT NULL AND TRIM(sku) <> ''
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_product_barcodes_store_barcode_unique
            ON product_barcodes (store_id, barcode)
            WHERE barcode IS NOT NULL AND TRIM(barcode) <> ''
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_store ON sales (store_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales (created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_user ON sales (user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_register ON sales (register_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_shift ON sales (shift_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_cloud ON sales (store_id, cloud_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_sync_status ON sales (store_id, sync_status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items (sale_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_store ON sale_items (store_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_payments_store ON sale_payments (store_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue (status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_store ON sync_queue (store_id)")
        connection.execute(
            """
            INSERT OR IGNORE INTO product_barcodes (product_id, barcode, is_primary, store_id)
            SELECT id, barcode, 1, store_id
            FROM products
            WHERE barcode IS NOT NULL AND TRIM(barcode) <> ''
            """
        )
        inventory_migrated_key = scoped_meta_key("inventory_model_v2_migrated", store_id)
        inventory_migrated = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?",
            (inventory_migrated_key,),
        ).fetchone()
        if inventory_migrated is None:
            connection.execute(
                """
                UPDATE products
                SET stock_qty = (
                    SELECT COUNT(*)
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                )
                WHERE COALESCE(stock_qty, 0) <= 0
                  AND EXISTS (
                      SELECT 1
                      FROM product_barcodes
                      WHERE product_barcodes.product_id = products.id
                  )
                """
            )
            connection.execute(
                "INSERT INTO app_meta (key, value) VALUES (?, 'true')",
                (inventory_migrated_key,),
            )
        if should_seed_demo_catalog(connection):
            seed_supermarket_catalog(connection)
            seed_supermarket_catalog_v2(connection)
            seed_supermarket_catalog_v3(connection)
        connection.commit()


def seed_supermarket_catalog(connection: sqlite3.Connection) -> None:
    store_id = current_store_id_from_connection(connection)
    seed_key = scoped_meta_key("supermarket_catalog_seed_v1", store_id)
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (seed_key,),
    ).fetchone()
    if seeded is not None:
        return

    catalog = [
        ("8901000000011", "Whole Milk 1L", 2.49, "Dairy", 48, False, "assets/products/milk.png"),
        ("8901000000028", "Fresh Bread Loaf", 1.99, "Bakery", 36, False, "assets/products/bread.png"),
        ("8901000000035", "Large Eggs 12 Pack", 3.79, "Dairy", 30, False, "assets/products/eggs.png"),
        ("8901000000042", "Bananas", 1.29, "Produce", 55, True, "assets/products/bananas.png"),
        ("8901000000059", "Red Apples", 1.89, "Produce", 60, True, "assets/products/apples.png"),
        ("8901000000066", "White Rice 1kg", 4.49, "Grains", 28, False, "assets/products/rice.png"),
        ("8901000000073", "Spaghetti Pasta 500g", 2.19, "Pantry", 42, False, "assets/products/pasta.png"),
        ("8901000000080", "Olive Oil 500ml", 7.99, "Pantry", 24, False, "assets/products/olive_oil.png"),
        ("8901000000097", "Chicken Breast 1kg", 8.99, "Meat", 20, True, "assets/products/chicken.png"),
        ("8901000000103", "Greek Yogurt 500g", 3.29, "Dairy", 34, False, "assets/products/yogurt.png"),
        ("8901000000110", "Orange Juice 1L", 3.49, "Beverages", 26, False, "assets/products/orange_juice.png"),
        ("8901000000127", "Corn Cereal 500g", 4.19, "Breakfast", 22, False, "assets/products/cereal.png"),
    ]

    for barcode, name, price, category, stock_qty, requires_weight, image_path in catalog:
        existing = connection.execute(
            """
            SELECT id
            FROM products
            WHERE store_id = ? AND barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.store_id = ?
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (store_id, barcode, store_id, barcode),
        ).fetchone()
        if existing is not None:
            continue

        cursor = connection.execute(
            """
            INSERT INTO products (
                store_id, barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (store_id, barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
            VALUES (?, ?, ?, 1)
            """,
            (store_id, product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, 'true')",
        (seed_key,),
    )


def seed_supermarket_catalog_v2(connection: sqlite3.Connection) -> None:
    store_id = current_store_id_from_connection(connection)
    seed_key = scoped_meta_key("supermarket_catalog_seed_v2", store_id)
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (seed_key,),
    ).fetchone()
    if seeded is not None:
        return

    catalog = [
        ("8901000000134", "Fresh Tomatoes", 1.59, "Produce", 45, True, "assets/products/tomatoes.png"),
        ("8901000000141", "Potatoes", 1.19, "Produce", 70, True, "assets/products/potatoes.png"),
        ("8901000000158", "Yellow Onions", 1.39, "Produce", 52, True, "assets/products/onions.png"),
        ("8901000000165", "Carrots 1kg", 1.79, "Produce", 40, False, "assets/products/carrots.png"),
        ("8901000000172", "Lettuce Head", 1.49, "Produce", 26, False, "assets/products/lettuce.png"),
        ("8901000000189", "Cheddar Cheese 250g", 3.99, "Dairy", 32, False, "assets/products/cheese.png"),
        ("8901000000196", "Butter 250g", 2.89, "Dairy", 30, False, "assets/products/butter.png"),
        ("8901000000202", "Mineral Water 1.5L", 0.99, "Beverages", 80, False, "assets/products/water.png"),
        ("8901000000219", "Sparkling Water 1L", 1.29, "Beverages", 48, False, "assets/products/sparkling_water.png"),
        ("8901000000226", "Ground Coffee 250g", 5.99, "Beverages", 24, False, "assets/products/coffee.png"),
        ("8901000000233", "Black Tea 100 Bags", 4.49, "Beverages", 20, False, "assets/products/tea.png"),
        ("8901000000240", "White Sugar 1kg", 2.19, "Pantry", 44, False, "assets/products/sugar.png"),
        ("8901000000257", "Wheat Flour 1kg", 1.89, "Pantry", 46, False, "assets/products/flour.png"),
        ("8901000000264", "Table Salt 750g", 0.89, "Pantry", 35, False, "assets/products/salt.png"),
        ("8901000000271", "Tomato Ketchup 500g", 2.79, "Condiments", 28, False, "assets/products/ketchup.png"),
        ("8901000000288", "Mayonnaise 500g", 3.19, "Condiments", 25, False, "assets/products/mayonnaise.png"),
        ("8901000000295", "Canned Tuna 160g", 2.49, "Canned Goods", 38, False, "assets/products/tuna.png"),
        ("8901000000301", "Salmon Fillet", 9.49, "Seafood", 18, True, "assets/products/salmon.png"),
        ("8901000000318", "Beef Steak", 10.99, "Meat", 16, True, "assets/products/beef.png"),
        ("8901000000325", "Hand Soap 500ml", 2.69, "Household", 27, False, "assets/products/soap.png"),
        ("8901000000332", "Shampoo 400ml", 4.99, "Personal Care", 21, False, "assets/products/shampoo.png"),
        ("8901000000349", "Toothpaste 120ml", 2.39, "Personal Care", 33, False, "assets/products/toothpaste.png"),
        ("8901000000356", "Chocolate Cookies 300g", 2.99, "Snacks", 31, False, "assets/products/cookies.png"),
        ("8901000000363", "Potato Chips 150g", 2.49, "Snacks", 36, False, "assets/products/chips.png"),
    ]

    for barcode, name, price, category, stock_qty, requires_weight, image_path in catalog:
        existing = connection.execute(
            """
            SELECT id
            FROM products
            WHERE store_id = ? AND barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.store_id = ?
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (store_id, barcode, store_id, barcode),
        ).fetchone()
        if existing is not None:
            continue
        cursor = connection.execute(
            """
            INSERT INTO products (
                store_id, barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (store_id, barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
            VALUES (?, ?, ?, 1)
            """,
            (store_id, product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, 'true')",
        (seed_key,),
    )


def seed_supermarket_catalog_v3(connection: sqlite3.Connection) -> None:
    store_id = current_store_id_from_connection(connection)
    seed_key = scoped_meta_key("supermarket_catalog_seed_v3", store_id)
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (seed_key,),
    ).fetchone()
    if seeded is not None:
        return

    catalog = [
        ("8901000000370", "Pears", 2.09, "Produce", 42, True, "assets/products/pears.png"),
        ("8901000000387", "Seedless Grapes", 2.99, "Produce", 28, True, "assets/products/grapes.png"),
        ("8901000000394", "Oranges", 2.29, "Produce", 40, True, "assets/products/oranges.png"),
        ("8901000000400", "Strawberries 250g", 3.49, "Produce", 24, False, "assets/products/strawberries.png"),
        ("8901000000417", "Cucumbers", 1.39, "Produce", 34, False, "assets/products/cucumbers.png"),
        ("8901000000424", "Broccoli", 1.89, "Produce", 26, False, "assets/products/broccoli.png"),
        ("8901000000431", "Sweet Corn", 1.59, "Produce", 30, False, "assets/products/corn.png"),
        ("8901000000448", "Mushrooms 250g", 2.19, "Produce", 22, False, "assets/products/mushrooms.png"),
        ("8901000000455", "Vanilla Ice Cream", 4.29, "Frozen", 20, False, "assets/products/ice_cream.png"),
        ("8901000000462", "Cooking Cream 250ml", 2.49, "Dairy", 25, False, "assets/products/cream.png"),
        ("8901000000479", "Cola Can 330ml", 1.19, "Beverages", 72, False, "assets/products/cola.png"),
        ("8901000000486", "Lemon Soda 330ml", 1.19, "Beverages", 64, False, "assets/products/lemon_soda.png"),
        ("8901000000493", "Energy Drink 250ml", 2.29, "Beverages", 40, False, "assets/products/energy_drink.png"),
        ("8901000000509", "Apple Juice 1L", 3.39, "Beverages", 26, False, "assets/products/apple_juice.png"),
        ("8901000000516", "Milk Chocolate 100g", 1.79, "Snacks", 48, False, "assets/products/chocolate.png"),
        ("8901000000523", "Salted Crackers 250g", 2.19, "Snacks", 34, False, "assets/products/crackers.png"),
        ("8901000000530", "Rolled Oats 500g", 2.69, "Breakfast", 29, False, "assets/products/oats.png"),
        ("8901000000547", "Strawberry Jam 350g", 3.19, "Pantry", 24, False, "assets/products/jam.png"),
        ("8901000000554", "Peanut Butter 340g", 3.79, "Pantry", 22, False, "assets/products/peanut_butter.png"),
        ("8901000000561", "Baked Beans 400g", 1.59, "Canned Goods", 36, False, "assets/products/beans.png"),
        ("8901000000578", "Red Lentils 1kg", 3.29, "Pantry", 27, False, "assets/products/lentils.png"),
        ("8901000000585", "Instant Noodles 5 Pack", 2.99, "Pantry", 32, False, "assets/products/instant_noodles.png"),
        ("8901000000592", "Frozen Pizza", 5.49, "Frozen", 18, False, "assets/products/frozen_pizza.png"),
        ("8901000000608", "Frozen Peas 500g", 2.49, "Frozen", 20, False, "assets/products/frozen_peas.png"),
        ("8901000000615", "Dish Soap 750ml", 2.89, "Household", 24, False, "assets/products/dish_soap.png"),
        ("8901000000622", "Laundry Detergent 2L", 7.49, "Household", 18, False, "assets/products/laundry_detergent.png"),
        ("8901000000639", "Paper Towels 4 Pack", 4.99, "Household", 20, False, "assets/products/paper_towels.png"),
        ("8901000000646", "Toilet Paper 8 Roll", 6.49, "Household", 22, False, "assets/products/toilet_paper.png"),
        ("8901000000653", "Deodorant Spray", 3.79, "Personal Care", 26, False, "assets/products/deodorant.png"),
        ("8901000000660", "Body Lotion 400ml", 4.59, "Personal Care", 20, False, "assets/products/lotion.png"),
        ("8901000000677", "Baby Wipes 80 Pack", 3.29, "Baby", 24, False, "assets/products/baby_wipes.png"),
        ("8901000000684", "Diapers Medium 30 Pack", 8.99, "Baby", 16, False, "assets/products/diapers.png"),
        ("8901000000691", "Cat Food 400g", 2.69, "Pet Care", 30, False, "assets/products/cat_food.png"),
        ("8901000000707", "Dog Food 2kg", 6.99, "Pet Care", 18, False, "assets/products/dog_food.png"),
        ("8901000000714", "Trash Bags 20 Pack", 4.29, "Household", 22, False, "assets/products/trash_bags.png"),
        ("8901000000721", "Aluminum Foil 20m", 3.19, "Household", 24, False, "assets/products/aluminum_foil.png"),
    ]

    for barcode, name, price, category, stock_qty, requires_weight, image_path in catalog:
        existing = connection.execute(
            """
            SELECT id
            FROM products
            WHERE store_id = ? AND barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.store_id = ?
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (store_id, barcode, store_id, barcode),
        ).fetchone()
        if existing is not None:
            continue
        cursor = connection.execute(
            """
            INSERT INTO products (
                store_id, barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (store_id, barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
            VALUES (?, ?, ?, 1)
            """,
            (store_id, product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, 'true')",
        (seed_key,),
    )


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


def fetch_barcodes_for_products(
    connection: sqlite3.Connection,
    product_ids: list[int],
) -> dict[int, list[str]]:
    if not product_ids:
        return {}

    placeholders = ",".join("?" for _ in product_ids)
    rows = connection.execute(
        f"""
        SELECT product_id, barcode
        FROM product_barcodes
        WHERE product_id IN ({placeholders})
        ORDER BY is_primary DESC, id ASC
        """,
        product_ids,
    ).fetchall()

    barcodes_by_product: dict[int, list[str]] = {product_id: [] for product_id in product_ids}
    for row in rows:
        barcodes_by_product.setdefault(int(row["product_id"]), []).append(str(row["barcode"]))
    return barcodes_by_product


def get_available_stock(product_id: int) -> float:
    """Return sellable stock from stock_qty, which is the inventory source of truth."""
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        row = connection.execute(
            """
            SELECT stock_qty
            FROM products
            WHERE active = 1 AND id = ? AND store_id = ?
            LIMIT 1
            """,
            (product_id, store_id),
        ).fetchone()
        if row is None:
            return 0.0

        return float(row["stock_qty"] or 0)


def is_barcode_available(barcode: str) -> bool:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return False

    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        row = connection.execute(
            """
            SELECT 1
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND p.store_id = ?
              AND (p.barcode = ? OR (pb.store_id = ? AND pb.barcode = ?))
            LIMIT 1
            """,
            (store_id, clean_barcode, store_id, clean_barcode),
        ).fetchone()
        return row is not None


def was_barcode_sold(barcode: str) -> bool:
    init_db()
    clean_barcode = barcode.strip()
    if not clean_barcode:
        return False

    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        row = connection.execute(
            """
            SELECT 1
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE si.barcode = ? AND si.store_id = ? AND s.store_id = ? AND s.status = 'completed'
            LIMIT 1
            """,
            (clean_barcode, store_id, store_id),
        ).fetchone()
        return row is not None


def get_available_stock_with_connection(connection: sqlite3.Connection, product_id: int) -> float:
    store_id = current_store_id_from_connection(connection)
    row = connection.execute(
        """
        SELECT stock_qty
        FROM products
        WHERE active = 1 AND id = ? AND store_id = ?
        LIMIT 1
        """,
        (product_id, store_id),
    ).fetchone()
    if row is None:
        return 0.0

    return float(row["stock_qty"] or 0)


def ensure_sale_items_available(connection: sqlite3.Connection, sale_items: list[dict[str, Any]]) -> None:
    requested_by_product: dict[int, float] = {}
    store_id = current_store_id_from_connection(connection)

    for item in sale_items:
        product_id = item.get("product_id")
        barcode = normalize_barcode(str(item.get("barcode") or ""))

        if barcode is not None:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND p.store_id = ?
                  AND (p.barcode = ? OR (pb.store_id = ? AND pb.barcode = ?))
                LIMIT 1
                """,
                (store_id, barcode, store_id, barcode),
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

    store_id = current_store_id_from_connection(connection)
    for product_id, sold_qty in sold_by_product.items():
        connection.execute(
            """
            UPDATE products
            SET stock_qty = MAX(COALESCE(stock_qty, 0) - ?, 0),
            updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND store_id = ?
            """,
            (sold_qty, product_id, store_id),
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


def product_rows_to_dicts(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    product_ids = [int(row["id"]) for row in rows]
    barcodes_by_product = fetch_barcodes_for_products(connection, product_ids)
    return [
        product_row_to_dict(row, barcodes_by_product.get(int(row["id"]), []))
        for row in rows
    ]


def get_all_products(limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        query = """
            SELECT id, store_id, cloud_id, barcode, name, price, category, stock_qty,
                   requires_weight, image_path, storage_path, image_url
            FROM products
            WHERE active = 1 AND store_id = ?
            ORDER BY id DESC
            """
        params: list[Any] = [store_id]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()
        return product_rows_to_dicts(connection, rows)


def search_products(
    keyword: str,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    init_db()
    clean_keyword = keyword.strip()
    if not clean_keyword:
        return get_all_products(limit=limit, offset=offset)

    search_value = f"%{clean_keyword}%"
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        query = """
            SELECT DISTINCT p.id, p.store_id, p.cloud_id, p.barcode, p.name, p.price,
                   p.category, p.stock_qty, p.requires_weight, p.image_path,
                   p.storage_path, p.image_url
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND p.store_id = ?
              AND (p.name LIKE ? OR p.barcode LIKE ? OR p.sku LIKE ? OR (pb.store_id = ? AND pb.barcode LIKE ?))
            ORDER BY p.name ASC, p.id DESC
            """
        params: list[Any] = [store_id, search_value, search_value, search_value, store_id, search_value]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()
        return product_rows_to_dicts(connection, rows)


def count_products(keyword: str = "") -> int:
    init_db()
    clean_keyword = keyword.strip()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        if not clean_keyword:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM products WHERE active = 1 AND store_id = ?",
                (store_id,),
            ).fetchone()
            return int(row["count"] if row else 0)

        search_value = f"%{clean_keyword}%"
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT p.id) AS count
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND p.store_id = ?
              AND (p.name LIKE ? OR p.barcode LIKE ? OR p.sku LIKE ? OR (pb.store_id = ? AND pb.barcode LIKE ?))
            """,
            (store_id, search_value, search_value, search_value, store_id, search_value),
        ).fetchone()
        return int(row["count"] if row else 0)


def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        row = connection.execute(
            """
            SELECT id, store_id, cloud_id, barcode, name, price, category, stock_qty,
                   requires_weight, image_path, storage_path, image_url
            FROM products
            WHERE active = 1 AND id = ? AND store_id = ?
            LIMIT 1
            """,
            (product_id, store_id),
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
        store_id = current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT p.id, p.store_id, p.cloud_id, p.barcode, p.name, p.price, p.category,
                   p.stock_qty, p.requires_weight, p.image_path, p.storage_path, p.image_url
            FROM products p
            LEFT JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE p.active = 1 AND p.store_id = ?
              AND (p.barcode = ? OR (pb.store_id = ? AND pb.barcode = ?))
            LIMIT 1
            """,
            (store_id, clean_barcode, store_id, clean_barcode),
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
        store_id = current_store_id_from_connection(connection)
        if exclude_product_id is None:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND p.store_id = ?
                  AND (p.barcode = ? OR (pb.store_id = ? AND pb.barcode = ?))
                LIMIT 1
                """,
                (store_id, clean_barcode, store_id, clean_barcode),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT 1
                FROM products p
                LEFT JOIN product_barcodes pb ON pb.product_id = p.id
                WHERE p.active = 1 AND p.store_id = ?
                  AND p.id <> ?
                  AND (p.barcode = ? OR (pb.store_id = ? AND pb.barcode = ?))
                LIMIT 1
                """,
                (store_id, exclude_product_id, clean_barcode, store_id, clean_barcode),
            ).fetchone()
        return row is not None


def add_product(
    name: str,
    price: float,
    category: str,
    stock_qty: float,
    requires_weight: bool,
    image_path: str,
    barcodes: list[str],
) -> int:
    init_db()
    normalized_barcodes = normalize_barcodes(barcodes)
    primary_barcode = normalized_barcodes[0] if normalized_barcodes else None
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        sync_status = "pending" if cloud_sync_enabled_for_store(store_id) else "local"
        cursor = connection.execute(
            """
            INSERT INTO products (
                store_id, barcode, name, price, category, stock_qty, requires_weight,
                image_path, sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                stock_qty,
                int(requires_weight),
                image_path.strip() or None,
                sync_status,
            ),
        )
        product_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
            VALUES (?, ?, ?, ?)
            """,
            [
                (store_id, product_id, barcode_value, int(index == 0))
                for index, barcode_value in enumerate(normalized_barcodes)
            ],
        )
        connection.commit()
    if sync_status == "pending":
        push_product_to_cloud(product_id)
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
    init_db()
    normalized_barcodes = normalize_barcodes(barcodes)
    primary_barcode = normalized_barcodes[0] if normalized_barcodes else None
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        sync_status = "pending" if cloud_sync_enabled_for_store(store_id) else "local"
        connection.execute(
            """
            UPDATE products
            SET barcode = ?, name = ?, price = ?, category = ?, stock_qty = ?, requires_weight = ?,
                image_path = ?, sync_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND store_id = ?
            """,
            (
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                stock_qty,
                int(requires_weight),
                image_path.strip() or None,
                sync_status,
                product_id,
                store_id,
            ),
        )
        connection.execute(
            "DELETE FROM product_barcodes WHERE product_id = ? AND store_id = ?",
            (product_id, store_id),
        )
        connection.executemany(
            """
            INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
            VALUES (?, ?, ?, ?)
            """,
            [
                (store_id, product_id, barcode_value, int(index == 0))
                for index, barcode_value in enumerate(normalized_barcodes)
            ],
        )
        connection.commit()
    if sync_status == "pending":
        push_product_to_cloud(product_id)


def delete_product(product_id: int) -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        sync_status = "pending" if cloud_sync_enabled_for_store(store_id) else "local"
        connection.execute(
            """
            UPDATE products
            SET active = 0, sync_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND store_id = ?
            """,
            (sync_status, product_id, store_id),
        )
        connection.commit()
    if sync_status == "pending":
        push_product_to_cloud(product_id)


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


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _payload_record(payload: Any) -> dict[str, Any]:
    data = _mapping_value(payload, "data") or payload
    record = _mapping_value(data, "record")
    return record if isinstance(record, dict) else {}


def _cloud_timestamp_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def should_ignore_product_realtime_event(payload: Any) -> bool:
    record = _payload_record(payload)
    store_id = str(record.get("store_id") or "")
    cloud_id = str(record.get("id") or "")
    cloud_updated_at = str(record.get("updated_at") or "")
    if not store_id or not cloud_id or not cloud_updated_at:
        return False

    with get_connection() as connection:
        current_store_id = current_store_id_from_connection(connection)
        if store_id != current_store_id:
            return True
        row = connection.execute(
            """
            SELECT sync_status, cloud_updated_at
            FROM products
            WHERE store_id = ? AND cloud_id = ?
            LIMIT 1
            """,
            (store_id, cloud_id),
        ).fetchone()

    if row is None or str(row["sync_status"] or "") != "synced":
        return False
    local_cloud_updated_at = str(row["cloud_updated_at"] or "")
    if not local_cloud_updated_at:
        return False
    return _cloud_timestamp_key(local_cloud_updated_at) >= _cloud_timestamp_key(cloud_updated_at)


def _product_sync_row(connection: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, store_id, cloud_id, barcode, sku, name, price, category, stock_qty,
               requires_weight, active, image_path, storage_path, image_url, sync_status
        FROM products
        WHERE id = ?
        LIMIT 1
        """,
        (product_id,),
    ).fetchone()


def _set_product_sync_state(
    connection: sqlite3.Connection,
    product_id: int,
    sync_status: str,
    cloud_id: str | None = None,
    storage_path: str | None = None,
    image_url: str | None = None,
    cloud_updated_at: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE products
        SET cloud_id = COALESCE(?, cloud_id),
            storage_path = COALESCE(?, storage_path),
            image_url = COALESCE(?, image_url),
            cloud_updated_at = COALESCE(?, cloud_updated_at),
            sync_status = ?,
            last_synced_at = CASE WHEN ? = 'synced' THEN CURRENT_TIMESTAMP ELSE last_synced_at END
        WHERE id = ?
        """,
        (cloud_id, storage_path, image_url, cloud_updated_at, sync_status, sync_status, product_id),
    )


def _cloud_payload_for_product(
    row: sqlite3.Row,
    storage_path: str | None,
    image_url: str | None,
) -> dict[str, Any]:
    return {
        "store_id": str(row["store_id"]),
        "barcode": row["barcode"],
        "sku": row["sku"],
        "name": str(row["name"] or "").strip(),
        "price": float(row["price"] or 0),
        "category": row["category"],
        "stock_qty": float(row["stock_qty"] or 0),
        "requires_weight": bool(row["requires_weight"]),
        "active": bool(row["active"]),
        "storage_path": storage_path,
        "image_url": image_url,
    }


def push_product_to_cloud(product_id: int) -> bool:
    init_db()
    with get_connection() as connection:
        row = _product_sync_row(connection, product_id)
        if row is None:
            return False
        store_id = str(row["store_id"] or "")
        if not cloud_sync_enabled_for_store(store_id):
            return False

    try:
        with get_connection() as connection:
            row = _product_sync_row(connection, product_id)
            if row is None:
                return False
            store_id = str(row["store_id"] or "")
            cloud_id = str(row["cloud_id"] or "") or None
            active = bool(row["active"])
            barcodes = fetch_product_barcodes(connection, product_id)

        if not active:
            cloud_row: dict[str, Any] | None = None
            if cloud_id:
                cloud_row = cloud_products.set_product_active(cloud_id, False)
            with get_connection() as connection:
                _set_product_sync_state(
                    connection,
                    product_id,
                    "synced",
                    cloud_id=cloud_id,
                    cloud_updated_at=str((cloud_row or {}).get("updated_at") or "") or None,
                )
                connection.commit()
            return True

        storage_path = str(row["storage_path"] or "") or None
        image_url = str(row["image_url"] or "") or None
        previous_cloud_stock: float | None = None
        if cloud_id:
            previous_cloud_product = cloud_products.fetch_product_stock(cloud_id)
            if previous_cloud_product is not None:
                previous_cloud_stock = float(previous_cloud_product.get("stock_qty") or 0)

        uploaded_storage_path, uploaded_image_url = cloud_products.upload_product_image(
            store_id,
            cloud_id or f"local-{product_id}",
            str(row["image_path"] or ""),
        )
        storage_path = uploaded_storage_path or storage_path
        image_url = uploaded_image_url or image_url

        cloud_row = cloud_products.upsert_product(
            _cloud_payload_for_product(row, storage_path, image_url),
            cloud_id=cloud_id,
        )
        cloud_id = str(cloud_row["id"])
        if previous_cloud_stock is not None:
            stock_delta = float(row["stock_qty"] or 0) - previous_cloud_stock
            cloud_products.record_inventory_adjustment(store_id, cloud_id, stock_delta, "adjustment")

        with get_connection() as connection:
            _set_product_sync_state(
                connection,
                product_id,
                "pending",
                cloud_id=cloud_id,
                storage_path=storage_path,
                image_url=image_url,
            )
            connection.commit()

        cloud_products.replace_product_barcodes(store_id, cloud_id, barcodes)

        with get_connection() as connection:
            _set_product_sync_state(
                connection,
                product_id,
                "synced",
                cloud_id=cloud_id,
                storage_path=storage_path,
                image_url=image_url,
                cloud_updated_at=str(cloud_row.get("updated_at") or "") or None,
            )
            connection.commit()
        return True
    except Exception:
        with get_connection() as connection:
            _set_product_sync_state(connection, product_id, "pending")
            connection.commit()
        return False


def retry_pending_product_sync(limit: int = 50) -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        if not cloud_sync_enabled_for_store(store_id):
            return
        rows = connection.execute(
            """
            SELECT id
            FROM products
            WHERE store_id = ? AND sync_status = 'pending'
            ORDER BY updated_at ASC, id ASC
            LIMIT ?
            """,
            (store_id, limit),
        ).fetchall()

    for row in rows:
        push_product_to_cloud(int(row["id"]))


def _upsert_cloud_product_local(
    connection: sqlite3.Connection,
    product: dict[str, Any],
    barcodes: list[str],
) -> None:
    store_id = str(product.get("store_id") or "")
    cloud_id = str(product.get("id") or "")
    if not store_id or not cloud_id:
        return

    existing = connection.execute(
        """
        SELECT id, sync_status, image_path
        FROM products
        WHERE store_id = ? AND cloud_id = ?
        LIMIT 1
        """,
        (store_id, cloud_id),
    ).fetchone()
    if existing is not None and str(existing["sync_status"] or "") == "pending":
        return

    image_path = str(existing["image_path"] or "") if existing is not None else ""
    image_url = str(product.get("image_url") or "")
    storage_path = str(product.get("storage_path") or "")
    cloud_updated_at = str(product.get("updated_at") or "") or None
    if image_url:
        try:
            image_path = cloud_products.download_product_image(store_id, cloud_id, image_url, storage_path)
        except Exception:
            image_path = image_path or image_url

    primary_barcode = str(product.get("barcode") or "")
    if not primary_barcode and barcodes:
        primary_barcode = barcodes[0]

    values = (
        store_id,
        cloud_id,
        primary_barcode or None,
        product.get("sku"),
        str(product.get("name") or "").strip(),
        float(product.get("price") or 0),
        product.get("category"),
        float(product.get("stock_qty") or 0),
        int(bool(product.get("requires_weight"))),
        int(bool(product.get("active", True))),
        image_path or None,
        storage_path or None,
        image_url or None,
        cloud_updated_at,
        "synced",
    )

    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO products (
                store_id, cloud_id, barcode, sku, name, price, category, stock_qty,
                requires_weight, active, image_path, storage_path, image_url,
                cloud_updated_at, sync_status, last_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            values,
        )
        local_product_id = int(cursor.lastrowid)
    else:
        local_product_id = int(existing["id"])
        connection.execute(
            """
            UPDATE products
            SET store_id = ?, cloud_id = ?, barcode = ?, sku = ?, name = ?, price = ?,
                category = ?, stock_qty = ?, requires_weight = ?, active = ?,
                image_path = ?, storage_path = ?, image_url = ?, cloud_updated_at = ?, sync_status = ?,
                last_synced_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            values + (local_product_id,),
        )

    connection.execute(
        "DELETE FROM product_barcodes WHERE store_id = ? AND product_id = ?",
        (store_id, local_product_id),
    )
    connection.executemany(
        """
        INSERT INTO product_barcodes (store_id, product_id, barcode, is_primary)
        VALUES (?, ?, ?, ?)
        """,
        [
            (store_id, local_product_id, barcode, int(index == 0))
            for index, barcode in enumerate(normalize_barcodes(barcodes))
        ],
    )


def pull_products_from_cloud() -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        if not cloud_sync_enabled_for_store(store_id):
            return

    products = cloud_products.fetch_products(store_id)
    barcode_rows = cloud_products.fetch_product_barcodes(store_id)
    barcodes_by_cloud_product: dict[str, list[str]] = {}
    for row in barcode_rows:
        if str(row.get("store_id") or "") != store_id:
            continue
        product_id = str(row.get("product_id") or "")
        barcode = str(row.get("barcode") or "").strip()
        if product_id and barcode:
            barcodes_by_cloud_product.setdefault(product_id, []).append(barcode)

    seen_cloud_ids: set[str] = set()
    with get_connection() as connection:
        for product in products:
            if str(product.get("store_id") or "") != store_id:
                continue
            cloud_id = str(product.get("id") or "")
            if not cloud_id:
                continue
            seen_cloud_ids.add(cloud_id)
            try:
                _upsert_cloud_product_local(
                    connection,
                    product,
                    barcodes_by_cloud_product.get(cloud_id, []),
                )
            except sqlite3.IntegrityError:
                continue

        if seen_cloud_ids:
            placeholders = ",".join("?" for _ in seen_cloud_ids)
            connection.execute(
                f"""
                UPDATE products
                SET active = 0, sync_status = 'synced', updated_at = CURRENT_TIMESTAMP
                WHERE store_id = ?
                  AND cloud_id IS NOT NULL
                  AND sync_status = 'synced'
                  AND cloud_id NOT IN ({placeholders})
                """,
                [store_id, *seen_cloud_ids],
            )
        else:
            connection.execute(
                """
                UPDATE products
                SET active = 0, sync_status = 'synced', updated_at = CURRENT_TIMESTAMP
                WHERE store_id = ?
                  AND cloud_id IS NOT NULL
                  AND sync_status = 'synced'
                """,
                (store_id,),
            )
        connection.commit()


def _current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_payment_rows(
    payment_method: str,
    payments: list[dict[str, Any]] | None,
    total_amount: float,
) -> list[dict[str, Any]]:
    rows = payments or [{"method": payment_method, "amount": total_amount}]
    return [
        {
            "method": str(payment.get("method") or payment_method or "Unknown"),
            "amount": float(payment.get("amount") or 0),
        }
        for payment in rows
        if float(payment.get("amount") or 0) > 0
    ] or [{"method": payment_method or "Unknown", "amount": float(total_amount or 0)}]


def _cloud_register_id_for_local(
    connection: sqlite3.Connection,
    register_id: int | None,
) -> int | None:
    if register_id is None:
        return None
    try:
        if not column_exists(connection, "registers", "cloud_id"):
            return None
        row = connection.execute(
            "SELECT cloud_id FROM registers WHERE id = ? LIMIT 1",
            (register_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if row is None or not str(row["cloud_id"] or "").strip():
        return None
    try:
        return int(str(row["cloud_id"]))
    except ValueError:
        return None


def _local_register_id_for_cloud(
    connection: sqlite3.Connection,
    store_id: str,
    cloud_register_id: Any,
) -> int | None:
    cloud_id = str(cloud_register_id or "").strip()
    if not cloud_id:
        return None
    try:
        if not column_exists(connection, "registers", "cloud_id"):
            return None
        row = connection.execute(
            "SELECT id FROM registers WHERE store_id = ? AND cloud_id = ? LIMIT 1",
            (store_id, cloud_id),
        ).fetchone()
    except sqlite3.Error:
        return None
    return int(row["id"]) if row is not None else None


def _local_user_id_for_cloud(
    connection: sqlite3.Connection,
    store_id: str,
    cloud_user_id: Any,
) -> int | None:
    cloud_id = str(cloud_user_id or "").strip()
    if not cloud_id:
        return None
    try:
        row = connection.execute(
            "SELECT id FROM users WHERE store_id = ? AND cloud_auth_id = ? LIMIT 1",
            (store_id, cloud_id),
        ).fetchone()
    except sqlite3.Error:
        return None
    return int(row["id"]) if row is not None else None


def _local_product_id_for_cloud(
    connection: sqlite3.Connection,
    store_id: str,
    cloud_product_id: Any,
) -> int | None:
    cloud_id = str(cloud_product_id or "").strip()
    if not cloud_id:
        return None
    row = connection.execute(
        "SELECT id FROM products WHERE store_id = ? AND cloud_id = ? LIMIT 1",
        (store_id, cloud_id),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def _cloud_sale_items_for_local_items(
    connection: sqlite3.Connection,
    store_id: str,
    sale_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cloud_items: list[dict[str, Any]] = []
    for item in sale_items:
        local_product_id = item.get("product_id")
        if local_product_id is None:
            raise ValueError("Every checkout item must be linked to a product before syncing.")

        row = connection.execute(
            """
            SELECT cloud_id, name
            FROM products
            WHERE id = ? AND store_id = ? AND active = 1
            LIMIT 1
            """,
            (int(local_product_id), store_id),
        ).fetchone()
        cloud_id = str(row["cloud_id"] or "").strip() if row is not None else ""
        if not cloud_id:
            raise ValueError(
                f"Product '{item.get('name') or local_product_id}' has not synced to Supabase yet. "
                "Sync products before checkout."
            )
        try:
            cloud_product_id: int | str = int(cloud_id)
        except ValueError:
            cloud_product_id = cloud_id

        cloud_items.append(
            {
                "product_id": cloud_product_id,
                "barcode": str(item.get("barcode") or ""),
                "name": str(item.get("name") or row["name"] or "Item"),
                "qty": float(item.get("qty") or 0),
                "price": float(item.get("price") or 0),
                "subtotal": float(item.get("subtotal") or 0),
            }
        )
    return cloud_items


def _save_sale_local(
    connection: sqlite3.Connection,
    store_id: str,
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
    client_uuid: str | None = None,
    cloud_id: str | None = None,
    status: str = "completed",
    sync_status: str = "local",
    sync_error: str | None = None,
    created_at: str | None = None,
    reduce_stock: bool = True,
) -> int:
    client_uuid = client_uuid or str(uuid.uuid4())
    payment_rows = normalize_payment_rows(payment_method, payments, total_amount)
    created_at_value = created_at or _current_timestamp()
    last_synced_at = _current_timestamp() if sync_status == "synced" else None

    existing = None
    if cloud_id:
        existing = connection.execute(
            "SELECT id FROM sales WHERE store_id = ? AND cloud_id = ? LIMIT 1",
            (store_id, cloud_id),
        ).fetchone()
    if existing is None:
        existing = connection.execute(
            "SELECT id FROM sales WHERE store_id = ? AND client_uuid = ? LIMIT 1",
            (store_id, client_uuid),
        ).fetchone()

    values = (
        store_id,
        cloud_id,
        client_uuid,
        user_id,
        register_id,
        shift_id,
        float(total_amount),
        payment_method,
        float(tendered_amount),
        float(change_amount),
        note.strip(),
        status,
        sync_status,
        sync_error,
        last_synced_at,
        created_at_value,
    )

    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO sales (
                store_id, cloud_id, client_uuid, user_id, register_id, shift_id,
                total_amount, payment_method, tendered_amount, change_amount,
                note, status, sync_status, sync_error, last_synced_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        sale_id = int(cursor.lastrowid)
    else:
        sale_id = int(existing["id"])
        connection.execute(
            """
            UPDATE sales
            SET store_id = ?, cloud_id = COALESCE(?, cloud_id), client_uuid = ?,
                user_id = ?, register_id = ?, shift_id = ?, total_amount = ?,
                payment_method = ?, tendered_amount = ?, change_amount = ?,
                note = ?, status = ?, sync_status = ?, sync_error = ?,
                last_synced_at = ?, created_at = ?
            WHERE id = ?
            """,
            values + (sale_id,),
        )
        connection.execute("DELETE FROM sale_items WHERE sale_id = ? AND store_id = ?", (sale_id, store_id))
        connection.execute("DELETE FROM sale_payments WHERE sale_id = ? AND store_id = ?", (sale_id, store_id))

    connection.executemany(
        """
        INSERT INTO sale_items (store_id, sale_id, product_id, barcode, name, qty, price, subtotal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                store_id,
                sale_id,
                item.get("product_id"),
                str(item.get("barcode") or ""),
                str(item.get("name") or ""),
                float(item.get("qty") or 0),
                float(item.get("price") or 0),
                float(item.get("subtotal") or 0),
            )
            for item in sale_items
        ],
    )
    connection.executemany(
        """
        INSERT INTO sale_payments (store_id, sale_id, method, amount)
        VALUES (?, ?, ?, ?)
        """,
        [(store_id, sale_id, payment["method"], payment["amount"]) for payment in payment_rows],
    )
    if reduce_stock:
        reduce_explicit_stock(connection, sale_items)

    if sync_status in {"local", "pending_offline", "conflict"}:
        connection.execute(
            """
            INSERT INTO sync_queue (store_id, entity_type, entity_id, operation, payload, status, last_error)
            VALUES (?, 'sale', ?, 'create', ?, ?, ?)
            """,
            (
                store_id,
                sale_id,
                f"sale_id={sale_id};client_uuid={client_uuid};total={total_amount:.2f}",
                "pending" if sync_status == "pending_offline" else sync_status,
                sync_error,
            ),
        )
    return sale_id


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
    init_db()
    if not sale_items:
        raise ValueError("Sale items are required.")
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        ensure_sale_items_available(connection, sale_items)
        sale_id = _save_sale_local(
            connection,
            store_id,
            total_amount,
            payment_method,
            sale_items,
            user_id=user_id,
            register_id=register_id,
            shift_id=shift_id,
            tendered_amount=tendered_amount,
            change_amount=change_amount,
            note=note,
            payments=payments,
            sync_status="local",
            reduce_stock=True,
        )
        connection.commit()
        return sale_id


def _set_sale_sync_state(
    connection: sqlite3.Connection,
    sale_id: int,
    sync_status: str,
    cloud_id: str | None = None,
    sync_error: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE sales
        SET cloud_id = COALESCE(?, cloud_id),
            sync_status = ?,
            sync_error = ?,
            last_synced_at = CASE WHEN ? = 'synced' THEN CURRENT_TIMESTAMP ELSE last_synced_at END
        WHERE id = ?
        """,
        (cloud_id, sync_status, sync_error, sync_status, sale_id),
    )


def checkout_sale_cloud_first(
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
    allow_offline: bool = False,
) -> dict[str, Any]:
    init_db()
    if not sale_items:
        raise ValueError("Sale items are required.")
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        ensure_sale_items_available(connection, sale_items)

    if not cloud_sync_enabled_for_store(store_id):
        sale_id = create_sale(
            total_amount,
            payment_method,
            sale_items,
            user_id=user_id,
            register_id=register_id,
            shift_id=shift_id,
            tendered_amount=tendered_amount,
            change_amount=change_amount,
            note=note,
            payments=payments,
        )
        return {"sale_id": sale_id, "sync_status": "local", "cloud_id": None}

    client_uuid = str(uuid.uuid4())
    payment_rows = normalize_payment_rows(payment_method, payments, total_amount)

    try:
        with get_connection() as connection:
            cloud_items = _cloud_sale_items_for_local_items(connection, store_id, sale_items)
            cloud_register_id = _cloud_register_id_for_local(connection, register_id)
        cloud_sale = cloud_inventory.checkout_sale(
            client_uuid,
            cloud_register_id,
            cloud_items,
            payment_rows,
            total_amount,
            note,
        )
        cloud_sale_id = str(cloud_sale.get("sale_id") or "")
        if not cloud_sale_id:
            raise ValueError("Supabase checkout did not return a sale id.")

        with get_connection() as connection:
            sale_id = _save_sale_local(
                connection,
                store_id,
                total_amount,
                payment_method,
                sale_items,
                user_id=user_id,
                register_id=register_id,
                shift_id=shift_id,
                tendered_amount=tendered_amount,
                change_amount=change_amount,
                note=note,
                payments=payment_rows,
                client_uuid=client_uuid,
                cloud_id=cloud_sale_id,
                sync_status="synced",
                reduce_stock=True,
            )
            connection.commit()

        sync_after_checkout()
        return {"sale_id": sale_id, "sync_status": "synced", "cloud_id": cloud_sale_id}
    except cloud_inventory.CloudInventoryConflict as error:
        try:
            pull_products_from_cloud()
        except Exception:
            pass
        raise ValueError(str(error)) from error
    except Exception as error:
        if not allow_offline:
            raise ValueError(
                "Cloud checkout is required for this store. Check the network and try again. "
                f"Details: {error}"
            ) from error

        with get_connection() as connection:
            sale_id = _save_sale_local(
                connection,
                store_id,
                total_amount,
                payment_method,
                sale_items,
                user_id=user_id,
                register_id=register_id,
                shift_id=shift_id,
                tendered_amount=tendered_amount,
                change_amount=change_amount,
                note=note,
                payments=payment_rows,
                client_uuid=client_uuid,
                sync_status="pending_offline",
                sync_error=str(error),
                reduce_stock=True,
            )
            connection.commit()
        return {
            "sale_id": sale_id,
            "sync_status": "pending_offline",
            "cloud_id": None,
            "sync_error": str(error),
        }


def _load_local_sale_for_sync(
    connection: sqlite3.Connection,
    sale_id: int,
) -> tuple[sqlite3.Row, list[dict[str, Any]], list[dict[str, Any]]] | None:
    sale = connection.execute(
        """
        SELECT id, store_id, cloud_id, client_uuid, user_id, register_id, shift_id,
               total_amount, payment_method, tendered_amount, change_amount,
               note, status, sync_status, created_at
        FROM sales
        WHERE id = ?
        LIMIT 1
        """,
        (sale_id,),
    ).fetchone()
    if sale is None:
        return None

    items = [
        row_to_dict(row)
        for row in connection.execute(
            """
            SELECT product_id, barcode, name, qty, price, subtotal
            FROM sale_items
            WHERE sale_id = ? AND store_id = ?
            ORDER BY id
            """,
            (sale_id, sale["store_id"]),
        ).fetchall()
    ]
    payments = [
        row_to_dict(row)
        for row in connection.execute(
            """
            SELECT method, amount
            FROM sale_payments
            WHERE sale_id = ? AND store_id = ?
            ORDER BY id
            """,
            (sale_id, sale["store_id"]),
        ).fetchall()
    ]
    return sale, items, payments


def push_pending_sale_to_cloud(sale_id: int) -> bool:
    init_db()
    try:
        with get_connection() as connection:
            payload = _load_local_sale_for_sync(connection, sale_id)
            if payload is None:
                return False
            sale, sale_items, payments = payload
            store_id = str(sale["store_id"] or "")
            if not cloud_sync_enabled_for_store(store_id):
                return False
            if str(sale["sync_status"] or "") != "pending_offline":
                return False
            cloud_items = _cloud_sale_items_for_local_items(connection, store_id, sale_items)
            cloud_register_id = _cloud_register_id_for_local(connection, sale["register_id"])

        client_uuid = str(sale["client_uuid"] or "") or str(uuid.uuid4())
        cloud_sale = cloud_inventory.checkout_sale(
            client_uuid,
            cloud_register_id,
            cloud_items,
            normalize_payment_rows(str(sale["payment_method"] or "Unknown"), payments, float(sale["total_amount"] or 0)),
            float(sale["total_amount"] or 0),
            str(sale["note"] or ""),
        )
        cloud_sale_id = str(cloud_sale.get("sale_id") or "")
        if not cloud_sale_id:
            raise ValueError("Supabase checkout did not return a sale id.")

        with get_connection() as connection:
            _set_sale_sync_state(connection, sale_id, "synced", cloud_id=cloud_sale_id)
            connection.execute(
                "UPDATE sync_queue SET status = 'synced', synced_at = CURRENT_TIMESTAMP WHERE entity_type = 'sale' AND entity_id = ?",
                (sale_id,),
            )
            connection.commit()
        sync_after_checkout()
        return True
    except cloud_inventory.CloudInventoryConflict as error:
        with get_connection() as connection:
            _set_sale_sync_state(connection, sale_id, "conflict", sync_error=str(error))
            connection.execute(
                """
                UPDATE sync_queue
                SET status = 'conflict', last_error = ?, retry_count = retry_count + 1
                WHERE entity_type = 'sale' AND entity_id = ?
                """,
                (str(error), sale_id),
            )
            connection.commit()
        try:
            pull_products_from_cloud()
        except Exception:
            pass
        return False
    except ValueError as error:
        with get_connection() as connection:
            _set_sale_sync_state(connection, sale_id, "pending_offline", sync_error=str(error))
            connection.commit()
        return False
    except Exception as error:
        with get_connection() as connection:
            _set_sale_sync_state(connection, sale_id, "pending_offline", sync_error=str(error))
            connection.execute(
                """
                UPDATE sync_queue
                SET last_error = ?, retry_count = retry_count + 1
                WHERE entity_type = 'sale' AND entity_id = ?
                """,
                (str(error), sale_id),
            )
            connection.commit()
        return False


def retry_pending_sale_sync(limit: int = 20) -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        if not cloud_sync_enabled_for_store(store_id):
            return
        rows = connection.execute(
            """
            SELECT id
            FROM sales
            WHERE store_id = ? AND sync_status = 'pending_offline'
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (store_id, limit),
        ).fetchall()

    for row in rows:
        push_pending_sale_to_cloud(int(row["id"]))


def _upsert_cloud_sale_local(
    connection: sqlite3.Connection,
    sale: dict[str, Any],
    sale_items: list[dict[str, Any]],
    payments: list[dict[str, Any]],
) -> None:
    store_id = str(sale.get("store_id") or "")
    cloud_id = str(sale.get("id") or "")
    if not store_id or not cloud_id:
        return

    local_items: list[dict[str, Any]] = []
    for item in sale_items:
        local_items.append(
            {
                "product_id": _local_product_id_for_cloud(connection, store_id, item.get("product_id")),
                "barcode": item.get("barcode"),
                "name": item.get("name"),
                "qty": float(item.get("qty") or 0),
                "price": float(item.get("price") or 0),
                "subtotal": float(item.get("subtotal") or 0),
            }
        )

    local_payments = [
        {
            "method": str(payment.get("method") or "Unknown"),
            "amount": float(payment.get("amount") or 0),
        }
        for payment in payments
    ]
    _save_sale_local(
        connection,
        store_id,
        float(sale.get("total_amount") or 0),
        str(sale.get("payment_method") or "Unknown"),
        local_items,
        user_id=_local_user_id_for_cloud(connection, store_id, sale.get("user_id")),
        register_id=_local_register_id_for_cloud(connection, store_id, sale.get("register_id")),
        tendered_amount=float(sale.get("tendered_amount") or 0),
        change_amount=float(sale.get("change_amount") or 0),
        note=str(sale.get("note") or ""),
        payments=local_payments,
        client_uuid=str(sale.get("client_sale_id") or ""),
        cloud_id=cloud_id,
        status=str(sale.get("status") or "completed"),
        sync_status="synced",
        created_at=str(sale.get("created_at") or "") or None,
        reduce_stock=False,
    )


def pull_recent_sales_from_cloud(limit: int = 200) -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        if not cloud_sync_enabled_for_store(store_id):
            return

    sales = cloud_inventory.fetch_recent_sales(store_id, limit=limit)
    sale_ids = [str(sale.get("id")) for sale in sales if sale.get("id") is not None]
    item_rows = cloud_inventory.fetch_sale_items(store_id, sale_ids)
    payment_rows = cloud_inventory.fetch_sale_payments(store_id, sale_ids)

    items_by_sale: dict[str, list[dict[str, Any]]] = {}
    for row in item_rows:
        items_by_sale.setdefault(str(row.get("sale_id") or ""), []).append(row)

    payments_by_sale: dict[str, list[dict[str, Any]]] = {}
    for row in payment_rows:
        payments_by_sale.setdefault(str(row.get("sale_id") or ""), []).append(row)

    with get_connection() as connection:
        for sale in sales:
            cloud_id = str(sale.get("id") or "")
            _upsert_cloud_sale_local(
                connection,
                sale,
                items_by_sale.get(cloud_id, []),
                payments_by_sale.get(cloud_id, []),
            )
        connection.commit()


def sync_after_checkout() -> None:
    try:
        pull_products_from_cloud()
    except Exception:
        pass
    try:
        pull_recent_sales_from_cloud(limit=50)
    except Exception:
        pass


def sync_now() -> None:
    retry_pending_product_sync()
    retry_pending_sale_sync()
    pull_products_from_cloud()
    pull_recent_sales_from_cloud()


def sync_realtime_update(kinds: set[str]) -> None:
    normalized = {str(kind).strip().lower() for kind in kinds if str(kind).strip()}
    if not normalized:
        return
    if "all" in normalized:
        normalized = {"products", "sales"}
    if "products" in normalized:
        pull_products_from_cloud()
    if "sales" in normalized:
        pull_recent_sales_from_cloud(limit=50)


def sync_on_login() -> None:
    sync_now()


def void_sale(sale_id: int) -> None:
    init_db()
    with get_connection() as connection:
        store_id = current_store_id_from_connection(connection)
        connection.execute(
            "UPDATE sales SET status = 'voided' WHERE id = ? AND store_id = ?",
            (sale_id, store_id),
        )
        connection.execute(
            """
            INSERT INTO sync_queue (store_id, entity_type, entity_id, operation, payload)
            VALUES (?, 'sale', ?, 'void', ?)
            """,
            (store_id, sale_id, f"sale_id={sale_id}"),
        )
        connection.commit()
