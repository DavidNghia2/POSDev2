import sqlite3
import hashlib
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app_branding import apply_app_icon, app_logo_pixmap
from ui.icon_manager import IconManager
from ui.theme import MODERN_WIDGET_STYLESHEET


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


def hash_password(password: str) -> str:
    return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_auth_db() -> None:
    with get_connection() as connection:
        # Create roles table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                permissions TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create users table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role_id INTEGER,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES roles (id)
            )
            """
        )
        
        # Create registers table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS registers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create cash_shifts table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cash_shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                register_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                opening_balance REAL DEFAULT 0,
                closing_balance REAL,
                expected_balance REAL,
                status TEXT DEFAULT 'open',
                FOREIGN KEY (register_id) REFERENCES registers (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        
        # Create cash_movements table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cash_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                user_id INTEGER,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shift_id) REFERENCES cash_shifts (id)
            )
            """
        )
        
        # Create audit_logs table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id INTEGER,
                old_values TEXT,
                new_values TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        
        # Create settings table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        add_column_if_missing(connection, "cash_movements", "user_id", "user_id INTEGER")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_roles_name ON roles (name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_registers_active ON registers (active)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_cash_shifts_status ON cash_shifts (status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_cash_shifts_register ON cash_shifts (register_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_cash_movements_shift ON cash_movements (shift_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs (created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue (status)")
        
        connection.commit()
        
        # Insert default roles if not exist
        cursor = connection.execute("SELECT COUNT(*) FROM roles")
        if cursor.fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO roles (name, permissions) VALUES (?, ?)",
                [
                    ("Admin", "all"),
                    ("Manager", "sales,reports,products,registers,shifts,reconciliation"),
                    ("Cashier", "sales,shifts"),
                ]
            )
        
        default_users = [
            ("admin", "admin123", "Administrator", 1),
            ("manager", "manager123", "Store Manager", 2),
            ("cashier", "cashier123", "Cashier", 3),
        ]
        for username, password, full_name, role_id in default_users:
            cursor = connection.execute(
                "SELECT COUNT(*) FROM users WHERE username = ?",
                (username,),
            )
            if cursor.fetchone()[0] == 0:
                connection.execute(
                    "INSERT INTO users (username, password_hash, full_name, role_id) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), full_name, role_id),
                )
        
        # Insert default register if not exists
        cursor = connection.execute("SELECT COUNT(*) FROM registers")
        if cursor.fetchone()[0] == 0:
            connection.execute(
                "INSERT INTO registers (name, location) VALUES (?, ?)",
                ("Main Register", "Store Front")
            )
        
        connection.commit()


def get_all_users() -> list[sqlite3.Row]:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT u.id, u.username, u.full_name, r.name as role_name, u.active, u.created_at
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            ORDER BY u.id DESC
            """
        )
        return cursor.fetchall()


def get_user_by_username(username: str) -> sqlite3.Row | None:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT u.id, u.username, u.password_hash, u.full_name, u.role_id, r.name as role_name, r.permissions
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.username = ? AND u.active = 1
            """,
            (username,),
        )
        return cursor.fetchone()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT u.id, u.username, u.password_hash, u.full_name, u.role_id, r.name as role_name, r.permissions
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = ? AND u.active = 1
            """,
            (user_id,),
        )
        return cursor.fetchone()


def verify_password(plain_password: str, stored_password: str) -> bool:
    if stored_password.startswith("sha256$"):
        return hash_password(plain_password) == stored_password
    return plain_password == stored_password


def has_permission(user: dict[str, Any], permission: str) -> bool:
    permissions = str(user.get("permissions") or "")
    return permissions == "all" or permission in {p.strip() for p in permissions.split(",")}


def get_all_roles() -> list[sqlite3.Row]:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute("SELECT id, name, permissions FROM roles ORDER BY id")
        return cursor.fetchall()


def get_all_registers() -> list[sqlite3.Row]:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute("SELECT id, name, location, active FROM registers WHERE active = 1 ORDER BY id")
        return cursor.fetchall()


def get_open_shift(register_id: int) -> sqlite3.Row | None:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, register_id, user_id, opened_at, opening_balance, status
            FROM cash_shifts
            WHERE register_id = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (register_id,),
        )
        return cursor.fetchone()


def open_cash_shift(register_id: int, user_id: int, opening_balance: float = 0) -> int:
    init_auth_db()
    existing_shift = get_open_shift(register_id)
    if existing_shift is not None:
        return int(existing_shift["id"])

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO cash_shifts (register_id, user_id, opening_balance, expected_balance, status)
            VALUES (?, ?, ?, ?, 'open')
            """,
            (register_id, user_id, opening_balance, opening_balance),
        )
        shift_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO cash_movements (shift_id, user_id, type, amount, reason)
            VALUES (?, ?, 'open', ?, 'Opening balance')
            """,
            (shift_id, user_id, opening_balance),
        )
        connection.commit()
        return shift_id


def add_cash_movement(shift_id: int, user_id: int, movement_type: str, amount: float, reason: str) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO cash_movements (shift_id, user_id, type, amount, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (shift_id, user_id, movement_type, amount, reason),
        )
        delta = amount if movement_type in {"open", "cash_in", "sale"} else -amount
        connection.execute(
            """
            UPDATE cash_shifts
            SET expected_balance = COALESCE(expected_balance, opening_balance, 0) + ?
            WHERE id = ? AND status = 'open'
            """,
            (delta, shift_id),
        )
        connection.commit()


def close_cash_shift(shift_id: int, user_id: int, closing_balance: float) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE cash_shifts
            SET closed_at = CURRENT_TIMESTAMP, closing_balance = ?, status = 'closed'
            WHERE id = ? AND status = 'open'
            """,
            (closing_balance, shift_id),
        )
        connection.execute(
            """
            INSERT INTO cash_movements (shift_id, user_id, type, amount, reason)
            VALUES (?, ?, 'close', ?, 'Closing balance')
            """,
            (shift_id, user_id, closing_balance),
        )
        connection.commit()


def add_user(username: str, password: str, full_name: str, role_id: int) -> int:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash, full_name, role_id) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), full_name, role_id),
        )
        connection.commit()
        return int(cursor.lastrowid)


def update_user(user_id: int, username: str, full_name: str, role_id: int, new_password: str | None = None) -> None:
    init_auth_db()
    with get_connection() as connection:
        if new_password:
            connection.execute(
                "UPDATE users SET username = ?, password_hash = ?, full_name = ?, role_id = ? WHERE id = ?",
                (username, hash_password(new_password), full_name, role_id, user_id),
            )
        else:
            connection.execute(
                "UPDATE users SET username = ?, full_name = ?, role_id = ? WHERE id = ?",
                (username, full_name, role_id, user_id),
            )
        connection.commit()


def delete_user(user_id: int) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
        connection.commit()


def add_register(name: str, location: str) -> int:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO registers (name, location) VALUES (?, ?)",
            (name, location),
        )
        connection.commit()
        return int(cursor.lastrowid)


def update_register(register_id: int, name: str, location: str) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute(
            "UPDATE registers SET name = ?, location = ? WHERE id = ?",
            (name, location, register_id),
        )
        connection.commit()


def delete_register(register_id: int) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute("UPDATE registers SET active = 0 WHERE id = ?", (register_id,))
        connection.commit()


def log_audit(user_id: int, action: str, table_name: str | None = None, record_id: int | None = None, 
             old_values: str | None = None, new_values: str | None = None) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO audit_logs (user_id, action, table_name, record_id, old_values, new_values) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, table_name, record_id, old_values, new_values),
        )
        connection.commit()


def get_audit_logs(limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT a.id, a.action, a.table_name, a.record_id, a.old_values, a.new_values, a.created_at,
                   u.username, u.full_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cursor.fetchall()


def get_setting(key: str) -> str | None:
    init_auth_db()
    with get_connection() as connection:
        cursor = connection.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, value),
        )
        connection.commit()


def build_user_payload(user: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role_id": user["role_id"],
        "role_name": user["role_name"],
        "permissions": user["permissions"],
    }


def save_session(user_id: int) -> None:
    set_setting("session_user_id", str(user_id))


def clear_session() -> None:
    init_auth_db()
    with get_connection() as connection:
        connection.execute("DELETE FROM settings WHERE key = 'session_user_id'")
        connection.commit()


def get_persisted_user() -> dict[str, Any] | None:
    user_id_text = get_setting("session_user_id")
    if not user_id_text:
        return None

    try:
        user_id = int(user_id_text)
    except ValueError:
        clear_session()
        return None

    user = get_user_by_id(user_id)
    if user is None:
        clear_session()
        return None
    return build_user_payload(user)


class PosIllustration(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(430, 360)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E6F4FF"))
        painter.drawEllipse(QRectF(w * 0.28, h * 0.07, w * 0.58, h * 0.72))
        painter.setBrush(QColor("#F2FAFF"))
        painter.drawEllipse(QRectF(w * 0.03, h * 0.47, w * 0.34, h * 0.32))

        counter_y = h * 0.77
        painter.setBrush(QColor("#D77B39"))
        painter.drawRoundedRect(QRectF(w * 0.05, counter_y - 12, w * 0.86, 18), 8, 8)
        painter.setBrush(QColor("#FFC8A3"))
        painter.drawRect(QRectF(w * 0.08, counter_y, w * 0.80, h * 0.20))

        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(QRectF(w * 0.25, h * 0.30, w * 0.38, h * 0.26), 12, 12)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(w * 0.28, h * 0.34, w * 0.32, h * 0.16), 9, 9)
        painter.setPen(QPen(QColor("#2563EB"), 3))
        painter.drawLine(int(w * 0.31), int(h * 0.39), int(w * 0.43), int(h * 0.39))
        painter.drawLine(int(w * 0.31), int(h * 0.45), int(w * 0.54), int(h * 0.45))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#94A3B8"))
        painter.drawRect(QRectF(w * 0.42, h * 0.56, w * 0.04, h * 0.18))
        painter.drawRoundedRect(QRectF(w * 0.30, h * 0.72, w * 0.27, h * 0.08), 8, 8)

        painter.setBrush(QColor("#0F172A"))
        scanner = QPainterPath()
        scanner.moveTo(w * 0.62, h * 0.53)
        scanner.lineTo(w * 0.77, h * 0.45)
        scanner.quadTo(w * 0.82, h * 0.47, w * 0.80, h * 0.54)
        scanner.lineTo(w * 0.68, h * 0.61)
        scanner.closeSubpath()
        painter.drawPath(scanner)
        painter.setBrush(QColor("#334155"))
        painter.drawRoundedRect(QRectF(w * 0.68, h * 0.60, w * 0.05, h * 0.16), 5, 5)
        painter.setPen(QPen(QColor("#60A5FA"), 2))
        painter.drawLine(int(w * 0.79), int(h * 0.47), int(w * 0.90), int(h * 0.36))
        painter.drawLine(int(w * 0.80), int(h * 0.51), int(w * 0.92), int(h * 0.48))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        receipt = QPainterPath()
        receipt.moveTo(w * 0.66, h * 0.16)
        receipt.lineTo(w * 0.84, h * 0.16)
        receipt.lineTo(w * 0.84, h * 0.50)
        receipt.lineTo(w * 0.81, h * 0.47)
        receipt.lineTo(w * 0.78, h * 0.50)
        receipt.lineTo(w * 0.75, h * 0.47)
        receipt.lineTo(w * 0.72, h * 0.50)
        receipt.lineTo(w * 0.69, h * 0.47)
        receipt.lineTo(w * 0.66, h * 0.50)
        receipt.closeSubpath()
        painter.drawPath(receipt)
        painter.setPen(QPen(QColor("#CBD5E1"), 2))
        for i in range(4):
            y = h * (0.23 + i * 0.055)
            painter.drawLine(int(w * 0.70), int(y), int(w * 0.80), int(y))
        painter.setPen(QPen(QColor("#22C55E"), 3))
        painter.drawLine(int(w * 0.70), int(h * 0.43), int(w * 0.74), int(h * 0.47))
        painter.drawLine(int(w * 0.74), int(h * 0.47), int(w * 0.81), int(h * 0.38))

        painter.setPen(Qt.PenStyle.NoPen)
        product_colors = ["#2563EB", "#0F766E", "#F97316"]
        for index, color in enumerate(product_colors):
            x = w * (0.12 + index * 0.10)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, h * 0.62, w * 0.075, h * 0.13), 6, 6)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(QRectF(x + 8, h * 0.65, w * 0.04, h * 0.018), 2, 2)


class ToggleSwitch(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 26)
        self.setText("")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_color = QColor("#4FD184") if self.isChecked() else QColor("#CBD5E1")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 1, 48, 24), 12, 12)

        knob_x = 24 if self.isChecked() else 3
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, 4, 18, 18))

        painter.setPen(QPen(QColor("#FFFFFF") if self.isChecked() else QColor("#64748B"), 2))
        if self.isChecked():
            painter.drawLine(12, 14, 16, 18)
            painter.drawLine(16, 18, 22, 10)
        else:
            painter.drawLine(30, 10, 36, 16)
            painter.drawLine(36, 10, 30, 16)


class RoleComboBox(QComboBox):
    """Combo box with a light popup container that matches the login form."""

    def showPopup(self) -> None:
        super().showPopup()
        popup_container = self.view().parentWidget()
        if popup_container is not None:
            popup_container.setStyleSheet(
                """
                background: #FFFFFF;
                border: 1px solid #DCE5F0;
                border-radius: 8px;
                """
            )


class LoginWindow(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.current_user: dict[str, Any] | None = None
        init_auth_db()
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("Retail POS - Sign In")
        apply_app_icon(self)
        self.setFixedSize(1040, 700)
        self.setModal(True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(44, 44, 44, 44)

        tablet = QFrame(self)
        tablet.setObjectName("tabletFrame")
        tablet_shadow = QGraphicsDropShadowEffect(tablet)
        tablet_shadow.setBlurRadius(44)
        tablet_shadow.setOffset(0, 16)
        tablet_shadow.setColor(QColor(15, 23, 42, 38))
        tablet.setGraphicsEffect(tablet_shadow)
        root_layout.addWidget(tablet)

        tablet_layout = QVBoxLayout(tablet)
        tablet_layout.setContentsMargins(82, 58, 62, 38)
        tablet_layout.setSpacing(18)

        heading = QHBoxLayout()
        heading.setSpacing(14)

        logo_label = QLabel()
        logo_label.setObjectName("brandLogo")
        logo_label.setFixedSize(54, 54)
        logo_label.setPixmap(app_logo_pixmap(54))

        heading_text = QVBoxLayout()
        heading_text.setSpacing(4)

        title_label = QLabel("Retail POS")
        title_label.setObjectName("appTitle")

        subtitle_label = QLabel("Inventory and sales management system")
        subtitle_label.setObjectName("appSubtitle")

        credit_label = QLabel("Created by DevTeam2 SWUST")
        credit_label.setObjectName("creatorCredit")

        heading_text.addWidget(title_label)
        heading_text.addWidget(subtitle_label)
        heading_text.addWidget(credit_label)
        heading.addWidget(logo_label)
        heading.addLayout(heading_text)
        heading.addStretch(1)
        tablet_layout.addLayout(heading)

        content = QHBoxLayout()
        content.setSpacing(34)
        tablet_layout.addLayout(content, 1)

        login_card = QFrame()
        login_card.setObjectName("loginCard")
        login_card.setFixedSize(360, 500)
        card_shadow = QGraphicsDropShadowEffect(login_card)
        card_shadow.setBlurRadius(34)
        card_shadow.setOffset(0, 16)
        card_shadow.setColor(QColor(15, 23, 42, 32))
        login_card.setGraphicsEffect(card_shadow)

        card_layout = QVBoxLayout(login_card)
        card_layout.setContentsMargins(34, 32, 34, 26)
        card_layout.setSpacing(11)

        login_title = IconManager.label("Login", "login", "loginTitle", icon_size=22)
        card_layout.addWidget(login_title)
        card_layout.addSpacing(10)

        username_row = QFrame()
        username_row.setObjectName("inputRow")
        username_row.setFixedHeight(48)
        username_layout = QHBoxLayout(username_row)
        username_layout.setContentsMargins(14, 0, 14, 0)
        username_layout.setSpacing(10)
        username_icon = self.create_inline_icon_label("user")
        username_separator = QFrame()
        username_separator.setObjectName("iconSeparator")
        username_separator.setFixedWidth(1)
        self.username_input = QLineEdit()
        self.username_input.setObjectName("cardInput")
        self.username_input.setPlaceholderText("Username")
        username_layout.addWidget(username_icon)
        username_layout.addWidget(username_separator)
        username_layout.addWidget(self.username_input, 1)

        password_row = QFrame()
        password_row.setObjectName("inputRow")
        password_row.setFixedHeight(48)
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(14, 0, 12, 0)
        password_layout.setSpacing(10)
        password_icon = self.create_inline_icon_label("lock")
        password_separator = QFrame()
        password_separator.setObjectName("iconSeparator")
        password_separator.setFixedWidth(1)
        self.password_input = QLineEdit()
        self.password_input.setObjectName("cardInput")
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.handle_login)
        self.password_toggle_button = QPushButton()
        self.password_toggle_button.setObjectName("passwordToggleButton")
        self.password_toggle_button.setCheckable(True)
        self.password_toggle_button.setFixedSize(20, 24)
        IconManager.apply_button(self.password_toggle_button, "eye_off", size=18)
        self.password_toggle_button.setToolTip("Show password")
        self.password_toggle_button.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(password_icon)
        password_layout.addWidget(password_separator)
        password_layout.addWidget(self.password_input, 1)
        password_layout.addWidget(
            self.password_toggle_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        card_layout.addWidget(username_row)
        card_layout.addWidget(password_row)
        role_row = QFrame()
        role_row.setObjectName("inputRow")
        role_row.setFixedHeight(48)
        role_layout = QHBoxLayout(role_row)
        role_layout.setContentsMargins(14, 0, 14, 0)
        role_layout.setSpacing(10)
        role_icon = self.create_inline_icon_label("role")
        role_separator = QFrame()
        role_separator.setObjectName("iconSeparator")
        role_separator.setFixedWidth(1)
        self.role_combo = RoleComboBox()
        self.role_combo.setObjectName("roleCombo")
        self.role_combo.setMinimumHeight(34)
        role_popup = QListView()
        role_popup.setObjectName("rolePopupView")
        role_popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        role_popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        role_popup.setSpacing(0)
        role_popup.setUniformItemSizes(True)
        self.role_combo.setView(role_popup)
        self.load_roles()
        self.configure_role_popup()
        role_layout.addWidget(role_icon)
        role_layout.addWidget(role_separator)
        role_layout.addWidget(self.role_combo, 1)
        card_layout.addWidget(role_row)
        card_layout.addSpacing(4)

        remember_layout = QHBoxLayout()
        remember_layout.setContentsMargins(0, 0, 0, 0)
        remember_layout.setSpacing(10)
        remember_label = QLabel("Keep me logged in")
        remember_label.setObjectName("rememberLabel")
        remember_label.setMinimumHeight(28)
        self.remember_checkbox = ToggleSwitch()
        self.remember_checkbox.setToolTip("Remember this login")
        self.remember_checkbox.setChecked(get_setting("remember_login") != "false")
        remember_layout.addWidget(remember_label)
        remember_layout.addWidget(self.remember_checkbox)
        remember_layout.addStretch()
        card_layout.addLayout(remember_layout)

        self.login_button = QPushButton("Log in")
        IconManager.apply_button(self.login_button, "login", IconManager.LIGHT)
        self.login_button.setObjectName("loginButton")
        self.login_button.setMinimumHeight(46)
        self.login_button.clicked.connect(self.handle_login)
        card_layout.addSpacing(14)
        card_layout.addWidget(self.login_button)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setMinimumHeight(20)
        card_layout.addWidget(self.error_label)
        card_layout.addStretch(1)

        content.addWidget(login_card, 0, Qt.AlignmentFlag.AlignVCenter)
        content.addWidget(PosIllustration(), 1, Qt.AlignmentFlag.AlignBottom)

        self.apply_styles()

    def load_roles(self) -> None:
        self.role_combo.clear()
        for role in get_all_roles():
            self.role_combo.addItem(role["name"], role["id"])

    def configure_role_popup(self) -> None:
        visible_roles = min(max(self.role_combo.count(), 3), 6)
        self.role_combo.setMaxVisibleItems(visible_roles)
        popup_row_height = max(self.role_combo.view().sizeHintForRow(0), 34)
        self.role_combo.view().setMinimumHeight((popup_row_height * visible_roles) + 14)

    def create_inline_icon_label(self, icon_key: str) -> QLabel:
        label = QLabel()
        label.setPixmap(IconManager.pixmap(icon_key, 20))
        label.setFixedSize(26, 26)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        selected_role = self.role_combo.currentText()
        
        if not username or not password:
            self.error_label.setText("Please enter username and password")
            return
        
        user = get_user_by_username(username)
        
        if user is None:
            self.error_label.setText("Invalid username or password")
            self.password_input.clear()
            return
        
        if not verify_password(password, user["password_hash"]):
            self.error_label.setText("Invalid username or password")
            self.password_input.clear()
            return

        if selected_role and user["role_name"] != selected_role:
            self.error_label.setText(f"This account is not assigned to {selected_role}")
            self.password_input.clear()
            return
        
        self.current_user = build_user_payload(user)

        remember_login = self.remember_checkbox.isChecked()
        set_setting("remember_login", "true" if remember_login else "false")
        if remember_login:
            save_session(int(user["id"]))
        else:
            clear_session()
        
        log_audit(user["id"], "LOGIN")
        self.accept()

    def toggle_password_visibility(self) -> None:
        if self.password_toggle_button.isChecked():
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.password_toggle_button.setIcon(IconManager.icon("eye"))
            self.password_toggle_button.setToolTip("Hide password")
            return

        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_toggle_button.setIcon(IconManager.icon("eye_off"))
        self.password_toggle_button.setToolTip("Show password")

    def get_user(self) -> dict[str, Any] | None:
        return self.current_user

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #DDE1E6;
            }

            QLabel {
                background: transparent;
            }

            #tabletFrame {
                background: #FFFFFF;
                border: 34px solid #F7F7F7;
                border-radius: 42px;
            }

            #appTitle {
                color: #050505;
                font-size: 30px;
                font-weight: 900;
            }

            #appSubtitle {
                color: #0F1115;
                font-size: 16px;
                font-weight: 700;
            }

            #creatorCredit {
                color: #64748B;
                font-size: 11px;
                font-weight: 600;
            }

            #loginCard {
                background: #FFFFFF;
                border-radius: 12px;
            }

            #loginTitle {
                color: #050505;
                font-size: 30px;
                font-weight: 900;
            }

            #inputRow {
                background: #FFFFFF;
                border: 1px solid #E1E6EE;
                border-radius: 7px;
            }

            #iconSeparator {
                background: #EEF1F5;
                border: none;
                min-height: 28px;
            }

            #cardInput {
                background: transparent;
                border: none;
                color: #111111;
                font-size: 14px;
                padding: 0;
                min-height: 34px;
            }

            #roleCombo {
                background: transparent;
                border: none;
                color: #111111;
                font-size: 14px;
                padding: 0;
            }

            #roleCombo::drop-down {
                border: none;
                width: 24px;
            }

            #roleCombo::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #5B91BB;
                width: 0;
                height: 0;
                margin-right: 8px;
            }

            #roleCombo QAbstractItemView {
                background: #FFFFFF;
                border: 1px solid #DCE5F0;
                border-radius: 8px;
                color: #111827;
                font-size: 14px;
                outline: none;
                padding: 4px;
                selection-background-color: transparent;
                selection-color: #111827;
            }

            #roleCombo QAbstractItemView::item {
                min-height: 34px;
                padding: 0 12px;
                border-radius: 6px;
            }

            #roleCombo QAbstractItemView::item:hover {
                background: #F5F8FC;
                color: #111827;
            }

            #roleCombo QAbstractItemView::item:selected {
                background: #EAF3FF;
                color: #1F77FF;
            }

            #passwordToggleButton {
                background: transparent;
                border: none;
                border-radius: 6px;
                min-width: 20px;
                max-width: 20px;
                min-height: 24px;
                max-height: 24px;
                padding: 0;
            }

            #passwordToggleButton:hover {
                background: #F2F7FF;
            }

            #rememberLabel {
                color: #1F2933;
                font-size: 13px;
                font-weight: 700;
            }

            #loginButton {
                background: #1F77FF;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 18px;
                font-weight: 800;
            }

            #loginButton:hover {
                background: #1768E8;
            }

            #loginButton:pressed {
                background: #1157C7;
            }

            #errorLabel {
                color: #DC2626;
                font-size: 12px;
                font-weight: 700;
            }

            """ + MODERN_WIDGET_STYLESHEET
        )


def show_login() -> dict[str, Any] | None:
    login_window = LoginWindow()
    if login_window.exec():
        return login_window.get_user()
    return None


if __name__ == "__main__":
    app = QApplication([])
    user = show_login()
    if user:
        print(f"Logged in as: {user['full_name']} ({user['role_name']})")
    else:
        print("Login cancelled")
