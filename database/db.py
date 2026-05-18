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
        add_column_if_missing(connection, "sales", "user_id", "user_id INTEGER")
        add_column_if_missing(connection, "sales", "register_id", "register_id INTEGER")
        add_column_if_missing(connection, "sales", "shift_id", "shift_id INTEGER")
        add_column_if_missing(connection, "sales", "tendered_amount", "tendered_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "change_amount", "change_amount REAL DEFAULT 0")
        add_column_if_missing(connection, "sales", "note", "note TEXT")
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
        inventory_migrated = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'inventory_model_v2_migrated'"
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
                "INSERT INTO app_meta (key, value) VALUES ('inventory_model_v2_migrated', 'true')"
            )
        seed_supermarket_catalog(connection)
        seed_supermarket_catalog_v2(connection)
        seed_supermarket_catalog_v3(connection)
        connection.commit()


def seed_supermarket_catalog(connection: sqlite3.Connection) -> None:
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = 'supermarket_catalog_seed_v1'"
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
            WHERE barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (barcode, barcode),
        ).fetchone()
        if existing is not None:
            continue

        cursor = connection.execute(
            """
            INSERT INTO products (
                barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (product_id, barcode, is_primary)
            VALUES (?, ?, 1)
            """,
            (product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES ('supermarket_catalog_seed_v1', 'true')"
    )


def seed_supermarket_catalog_v2(connection: sqlite3.Connection) -> None:
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = 'supermarket_catalog_seed_v2'"
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
            WHERE barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (barcode, barcode),
        ).fetchone()
        if existing is not None:
            continue
        cursor = connection.execute(
            """
            INSERT INTO products (
                barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (product_id, barcode, is_primary)
            VALUES (?, ?, 1)
            """,
            (product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES ('supermarket_catalog_seed_v2', 'true')"
    )


def seed_supermarket_catalog_v3(connection: sqlite3.Connection) -> None:
    seeded = connection.execute(
        "SELECT value FROM app_meta WHERE key = 'supermarket_catalog_seed_v3'"
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
            WHERE barcode = ?
               OR EXISTS (
                    SELECT 1
                    FROM product_barcodes
                    WHERE product_barcodes.product_id = products.id
                      AND product_barcodes.barcode = ?
               )
            LIMIT 1
            """,
            (barcode, barcode),
        ).fetchone()
        if existing is not None:
            continue
        cursor = connection.execute(
            """
            INSERT INTO products (
                barcode, name, price, category, stock_qty, requires_weight, image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (barcode, name, price, category, stock_qty, int(requires_weight), image_path),
        )
        product_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO product_barcodes (product_id, barcode, is_primary)
            VALUES (?, ?, 1)
            """,
            (product_id, barcode),
        )

    connection.execute(
        "INSERT INTO app_meta (key, value) VALUES ('supermarket_catalog_seed_v3', 'true')"
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


def get_available_stock(product_id: int) -> float:
    """Return sellable stock from stock_qty, which is the inventory source of truth."""
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

        return float(row["stock_qty"] or 0)


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

    return float(row["stock_qty"] or 0)


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
            SET stock_qty = MAX(COALESCE(stock_qty, 0) - ?, 0),
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
    stock_qty: float,
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
            INSERT INTO products (barcode, name, price, category, stock_qty, requires_weight, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                stock_qty,
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
    stock_qty: float,
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
            SET barcode = ?, name = ?, price = ?, category = ?, stock_qty = ?, requires_weight = ?,
                image_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                primary_barcode,
                name.strip(),
                price,
                category.strip(),
                stock_qty,
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
    note: str = "",
    payments: list[dict[str, Any]] | None = None,
) -> int:
    init_db()
    with get_connection() as connection:
        ensure_sale_items_available(connection, sale_items)
        cursor = connection.execute(
            """
            INSERT INTO sales (
                user_id, register_id, shift_id, total_amount, payment_method,
                tendered_amount, change_amount, note, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            """,
            (
                user_id,
                register_id,
                shift_id,
                total_amount,
                payment_method,
                tendered_amount,
                change_amount,
                note.strip(),
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
