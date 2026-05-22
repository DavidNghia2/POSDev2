from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import wrap

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QDoubleValidator, QFont, QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import db
from ui.currency import (
    format_money as format_currency,
    get_currency_symbol_from_settings,
    parse_money_text,
    refresh_money_widgets,
    set_money_label,
    set_money_table_item,
)
from ui.icon_manager import IconManager

# Admin imports
from admin.admin_dashboard_window import create_admin_dashboard
from admin.user_management_window import create_user_management
from admin.register_management_window import create_register_management
from admin.reports_window import create_reports
from admin.audit_logs_window import create_audit_logs
from admin.settings_window import create_settings

from login import add_cash_movement, clear_session, get_setting, has_permission, log_audit, open_cash_shift
from ui.app_branding import apply_app_icon, app_logo_pixmap
from ui.qr_display import qr_focus_pixmap
from ui.theme import MODERN_WIDGET_STYLESHEET
from ui.thumbnail_cache import ThumbnailCache


ACCENT_BLUE = "#2563EB"
ACCENT_GREEN = "#0F766E"
ACCENT_ORANGE = "#F97316"
TEXT_DARK = "#1F2937"
TEXT_MUTED = "#5F6B7A"
BORDER = "#D7DEE8"
PANEL_BG = "#F5F7FA"
WINDOW_BG = "#EEF2F6"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAYMENT_QR_DISPLAY_SIZE = 280
SPLIT_PAYMENT_QR_DISPLAY_SIZE = 210
POS_PRODUCT_GRID_LIMIT = 120


@dataclass
class CartItem:
    product_id: int
    barcode: str
    name: str
    qty: float
    unit_price: float
    requires_weight: bool = False

    @property
    def subtotal(self) -> float:
        return self.qty * self.unit_price


class SidebarButton(QPushButton):
    def __init__(self, text: str, icon, active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.expanded_text = text
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icon)
        self.setIconSize(QSize(18, 18))
        self.setToolTip(text)
        self.setProperty("active", active)
        self.setProperty("collapsed", False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_collapsed(self, collapsed: bool) -> None:
        self.setText("" if collapsed else self.expanded_text)
        self.setProperty("collapsed", collapsed)
        self.style().unpolish(self)
        self.style().polish(self)


class CollapsibleSidebar(QFrame):
    EXPANDED_WIDTH = 230
    COLLAPSED_WIDTH = 0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setProperty("collapsed", False)
        self.setFixedWidth(self.EXPANDED_WIDTH)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self.setVisible(False)
        else:
            self.setVisible(True)
            self.setFixedWidth(self.EXPANDED_WIDTH)
        self.setProperty("collapsed", collapsed)
        self.style().unpolish(self)
        self.style().polish(self)


class KeypadButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)


class ActionButton(QPushButton):
    def __init__(self, text: str, style_name: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("role", style_name)
        self.setMinimumHeight(42)


class DashboardCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("dashboardCardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("dashboardCardValue")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("dashboardCardSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(subtitle_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class PosMainWindow(QMainWindow):
    app_data_changed = pyqtSignal()

    def __init__(self, user_data: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("POS Sales Terminal")
        apply_app_icon(self)
        self.resize(1420, 860)
        self.setMinimumSize(1180, 720)

        # User authentication data
        self.user_data = user_data or {
            "id": 0,
            "username": "system",
            "full_name": "System",
            "role_id": 0,
            "role_name": "Admin",
            "permissions": "all",
        }

        db.init_db()
        self.cart_items: list[CartItem] = []
        self.register_id = 1
        self.shift_id = open_cash_shift(self.register_id, int(self.user_data.get("id", 0)), 0)

        self.search_input: QLineEdit
        self.cart_table: QTableWidget
        self.tender_input: QLineEdit
        self.total_value_label: QLabel
        self.sidebar_buttons: list[tuple[SidebarButton, int]] = []
        self.cart_table_updating = False
        self.admin_pages: dict = {}
        self.page_indexes: dict[str, int] = {}
        self.product_management_placeholder: QWidget | None = None
        self.sidebar_collapsed = False
        self.sidebar_widget: CollapsibleSidebar | None = None
        self.sidebar_layout: QVBoxLayout | None = None
        self.sidebar_expanded_widgets: list[QWidget] = []
        self.sidebar_toggle_button: QPushButton | None = None
        self.central_container: QWidget | None = None
        self.logout_button: QPushButton | None = None
        self.logout_requested = False
        self.reset_toast: QLabel | None = None
        self.reset_toast_effect: QGraphicsOpacityEffect | None = None
        self.reset_toast_animation: QPropertyAnimation | None = None

        self.build_ui()
        self.connect_global_refresh()
        self.start_shared_data_refresh()
        self.populate_cart()
        self.create_shortcuts()

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        self.central_container = central

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.pages = QStackedWidget()
        role_name = self.user_data.get("role_name")

        if role_name == "Cashier":
            self.page_indexes["cashier_dashboard"] = self.pages.addWidget(
                self.create_cashier_dashboard()
            )
        elif role_name == "Manager":
            self.page_indexes["manager_dashboard"] = self.pages.addWidget(
                self.create_manager_dashboard()
            )

        self.pos_terminal_page = self.create_content_area()
        self.page_indexes["pos_terminal"] = self.pages.addWidget(self.pos_terminal_page)

        self.product_management_page = None
        if has_permission(self.user_data, "products"):
            self.product_management_placeholder = QWidget()
            self.page_indexes["products"] = self.pages.addWidget(self.product_management_placeholder)

        if role_name == "Admin":
            self.admin_pages = {
                "admin_dashboard": create_admin_dashboard(self.user_data),
                "users": create_user_management(self.user_data),
                "registers": create_register_management(self.user_data),
                "reports": create_reports(self.user_data),
                "audit_logs": create_audit_logs(self.user_data),
                "settings": create_settings(self.user_data),
            }
        elif role_name == "Manager":
            self.admin_pages = {
                "reports": create_reports(self.user_data),
                "registers": create_register_management(self.user_data),
                "audit_logs": create_audit_logs(self.user_data),
            }

        for key, page in self.admin_pages.items():
            self.page_indexes[key] = self.pages.addWidget(page)

        root_layout.addWidget(self.create_sidebar())
        root_layout.addWidget(self.pages, 1)
        self.create_sidebar_toggle_button()

    def connect_global_refresh(self) -> None:
        self.app_data_changed.connect(self.reload_data)

        for page_index in range(self.pages.count()):
            self.connect_page_refresh(self.pages.widget(page_index))

    def connect_page_refresh(self, page: QWidget) -> None:
        reload_handler = self.get_reload_handler(page)
        if reload_handler is not None:
            self.app_data_changed.connect(reload_handler)

        data_changed_signal = getattr(page, "data_changed", None)
        if data_changed_signal is not None:
            data_changed_signal.connect(self.notify_app_data_changed)

    def get_reload_handler(self, page: QWidget):
        for method_name in (
            "reload_data",
            "load_dashboard_data",
            "load_products",
            "load_users",
            "load_registers",
            "load_settings",
            "load_report",
            "load_logs",
        ):
            handler = getattr(page, method_name, None)
            if callable(handler):
                return handler
        return None

    def notify_app_data_changed(self) -> None:
        self.app_data_changed.emit()

    def ensure_product_management_page(self) -> QWidget | None:
        products_index = self.page_indexes.get("products")
        if products_index is None:
            return None
        if self.product_management_page is not None:
            return self.product_management_page

        from product_management.product_management_window import ProductManagementWindow

        page = ProductManagementWindow()
        old_page = self.pages.widget(products_index)
        self.pages.removeWidget(old_page)
        old_page.deleteLater()
        self.pages.insertWidget(products_index, page)
        self.product_management_page = page
        self.connect_page_refresh(page)
        return page

    def start_shared_data_refresh(self) -> None:
        self.shared_data_refresh_timer = QTimer(self)
        self.shared_data_refresh_timer.setInterval(5000)
        self.shared_data_refresh_timer.timeout.connect(self.notify_app_data_changed)
        self.shared_data_refresh_timer.start()

    def reload_data(self) -> None:
        if hasattr(self, "search_input"):
            self.load_product_grid()
        self.refresh_total()
        refresh_money_widgets(self, self.get_currency_symbol())

    def get_setting_bool(self, key: str, default: bool = True) -> bool:
        value = get_setting(key)
        if value is None:
            return default
        return value.strip().lower() not in {"false", "0", "no", "off"}

    def get_currency_symbol(self) -> str:
        return get_currency_symbol_from_settings(get_setting)

    def format_money(self, amount: float, currency_symbol: str | None = None) -> str:
        symbol = currency_symbol if currency_symbol is not None else self.get_currency_symbol()
        return format_currency(amount, symbol)

    def resolve_setting_path(self, path_value: str) -> Path | None:
        if not path_value:
            return None

        path = Path(path_value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path if path.exists() else None

    def get_receipt_settings(self) -> dict[str, str]:
        return {
            "store_name": get_setting("store_name") or "",
            "store_address": get_setting("store_address") or "",
            "store_phone": get_setting("store_phone") or "",
            "store_email": get_setting("store_email") or "",
            "currency_symbol": self.get_currency_symbol(),
            "receipt_header": get_setting("receipt_header") or "",
            "receipt_footer": get_setting("receipt_footer") or "",
        }

    def get_payment_settings(self) -> dict[str, object]:
        return {
            "enable_bank_transfer": self.get_setting_bool("enable_bank_transfer", True),
            "bank_qr_path": self.resolve_setting_path(get_setting("bank_qr_image_path") or ""),
            "bank_name": get_setting("bank_name") or "",
            "account_name": get_setting("account_name") or get_setting("bank_account_name") or "",
            "account_number": get_setting("account_number") or get_setting("bank_account_number") or "",
        }

    def create_bank_qr_panel(
        self,
        payment_settings: dict[str, object] | None = None,
        qr_size: int = PAYMENT_QR_DISPLAY_SIZE,
        title: str = "Scan Bank Transfer QR",
    ) -> QFrame:
        payment_settings = payment_settings or self.get_payment_settings()
        bank_transfer_enabled = bool(payment_settings["enable_bank_transfer"])
        bank_qr_path = payment_settings["bank_qr_path"]
        bank_name = str(payment_settings["bank_name"])
        account_name = str(payment_settings["account_name"])
        account_number = str(payment_settings["account_number"])

        bank_qr_panel = QFrame()
        bank_qr_panel.setObjectName("paymentQrPanel")
        bank_qr_layout = QVBoxLayout(bank_qr_panel)
        bank_qr_layout.setContentsMargins(14, 14, 14, 14)
        bank_qr_layout.setSpacing(10)

        qr_title = QLabel(title)
        qr_title.setObjectName("paymentFieldLabel")
        qr_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_message = (
            "No QR image configured"
            if bank_transfer_enabled
            else "Bank Transfer disabled in Settings"
        )
        qr_image_label = QLabel(empty_message)
        qr_image_label.setObjectName("paymentQrPreview")
        qr_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_image_label.setFixedSize(qr_size, qr_size)
        qr_image_label.setWordWrap(True)

        if bank_transfer_enabled and isinstance(bank_qr_path, Path):
            qr_pixmap = qr_focus_pixmap(bank_qr_path, qr_size)
            if not qr_pixmap.isNull():
                qr_image_label.setText("")
                qr_image_label.setPixmap(qr_pixmap)

        bank_detail_lines = []
        if bank_name:
            bank_detail_lines.append(f"Bank: {bank_name}")
        if account_name:
            bank_detail_lines.append(f"Account: {account_name}")
        if account_number:
            bank_detail_lines.append(f"No: {account_number}")

        bank_detail_text = "\n".join(bank_detail_lines)
        if not bank_detail_text:
            bank_detail_text = (
                "Add bank details in Settings."
                if bank_transfer_enabled
                else "Enable Bank Transfer in Settings to use QR payment."
            )

        bank_detail_label = QLabel(bank_detail_text)
        bank_detail_label.setObjectName("paymentQrDetails")
        bank_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bank_detail_label.setWordWrap(True)

        bank_qr_layout.addWidget(qr_title, 0, Qt.AlignmentFlag.AlignCenter)
        bank_qr_layout.addWidget(qr_image_label, 0, Qt.AlignmentFlag.AlignCenter)
        bank_qr_layout.addWidget(bank_detail_label)
        return bank_qr_panel

    def get_today_summary(self) -> dict[str, float | int]:
        today = datetime.now().strftime("%Y-%m-%d")
        with db.get_connection() as connection:
            sales_row = connection.execute(
                """
                SELECT COUNT(*) AS count, COALESCE(SUM(total_amount), 0) AS total
                FROM sales
                WHERE date(created_at, 'localtime') = date(?) AND status = 'completed'
                """,
                (today,),
            ).fetchone()
            items_row = connection.execute(
                """
                SELECT COALESCE(SUM(si.qty), 0) AS items
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE date(s.created_at, 'localtime') = date(?) AND s.status = 'completed'
                """,
                (today,),
            ).fetchone()

        count = int(sales_row["count"] if sales_row else 0)
        total = float(sales_row["total"] if sales_row else 0)
        return {
            "sales_count": count,
            "sales_total": total,
            "items_sold": float(items_row["items"] if items_row else 0),
            "average_sale": total / count if count else 0,
        }

    def create_dashboard_card(self, title: str, value: str, subtitle: str) -> DashboardCard:
        return DashboardCard(title, value, subtitle)

    def create_dashboard_button(self, text: str, page_key: str, style_name: str = "primary") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("dashboardActionButton")
        button.setProperty("role", style_name)
        button.setMinimumHeight(42)
        page_icon = {
            "pos_terminal": "terminal",
            "reports": "reports",
            "registers": "registers",
            "products": "products",
        }.get(page_key)
        if page_icon is not None:
            IconManager.apply_button(button, page_icon, IconManager.LIGHT)
        button.clicked.connect(lambda _checked=False, key=page_key: self.switch_page(self.page_indexes[key]))
        return button

    def create_cashier_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = IconManager.label("Cashier Dashboard", "dashboard", "workspaceTitle", icon_size=20)
        subtitle = QLabel(
            f"Welcome {self.user_data.get('full_name', 'Cashier')} | Register #{self.register_id} | Shift #{self.shift_id}"
        )
        subtitle.setObjectName("cashierInfo")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        sales_count_card = self.create_dashboard_card("Today's Sales", "0", "Transactions completed")
        revenue_card = self.create_dashboard_card("Revenue", self.format_money(0), "Collected today")
        items_sold_card = self.create_dashboard_card("Items Sold", "0", "Units and weighted items")
        stats.addWidget(sales_count_card)
        stats.addWidget(revenue_card)
        stats.addWidget(items_sold_card)
        layout.addLayout(stats)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.create_dashboard_button("Open POS Terminal", "pos_terminal", "primary"))
        actions.addWidget(self.create_dashboard_button("Continue Shift", "pos_terminal", "secondary"))
        layout.addLayout(actions)
        layout.addStretch()

        def reload_dashboard() -> None:
            summary = self.get_today_summary()
            sales_count_card.set_value(f"{summary['sales_count']}")
            revenue_card.set_value(self.format_money(float(summary["sales_total"])))
            items_sold_card.set_value(f"{summary['items_sold']:g}")

        page.reload_data = reload_dashboard  # type: ignore[attr-defined]
        reload_dashboard()
        return page

    def create_manager_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = IconManager.label("Manager Dashboard", "dashboard", "workspaceTitle", icon_size=20)
        subtitle = QLabel("Monitor sales, registers, shift activity, and daily performance")
        subtitle.setObjectName("cashierInfo")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        revenue_card = self.create_dashboard_card("Revenue", self.format_money(0), "Completed sales today")
        transactions_card = self.create_dashboard_card("Transactions", "0", "Sales count today")
        average_sale_card = self.create_dashboard_card("Avg. Sale", self.format_money(0), "Average transaction")
        stats.addWidget(revenue_card)
        stats.addWidget(transactions_card)
        stats.addWidget(average_sale_card)
        layout.addLayout(stats)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.create_dashboard_button("View Reports", "reports", "primary"))
        actions.addWidget(self.create_dashboard_button("Manage Registers", "registers", "secondary"))
        if "products" in self.page_indexes:
            actions.addWidget(self.create_dashboard_button("Product Management", "products", "secondary"))
        layout.addLayout(actions)
        layout.addStretch()

        def reload_dashboard() -> None:
            summary = self.get_today_summary()
            revenue_card.set_value(self.format_money(float(summary["sales_total"])))
            transactions_card.set_value(f"{summary['sales_count']}")
            average_sale_card.set_value(self.format_money(float(summary["average_sale"])))

        page.reload_data = reload_dashboard  # type: ignore[attr-defined]
        reload_dashboard()
        return page

    def create_sidebar(self) -> QWidget:
        sidebar = CollapsibleSidebar()
        self.sidebar_widget = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(10)
        self.sidebar_layout = layout

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(10)

        logo_label = QLabel()
        logo_label.setObjectName("brandLogo")
        logo_label.setFixedSize(42, 42)
        logo_label.setPixmap(app_logo_pixmap(42))

        brand_text_widget = QWidget()
        brand_text_widget.setObjectName("sidebarBrandText")
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(1)
        brand_text_widget.setLayout(brand_text)

        title = QLabel("Retail POS")
        title.setObjectName("appTitle")

        subtitle = QLabel("Sales Terminal")
        subtitle.setObjectName("appSubtitle")

        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_row.addWidget(logo_label)
        brand_row.addWidget(brand_text_widget, 1)

        self.sidebar_expanded_widgets = [logo_label, brand_text_widget]
        layout.addLayout(brand_row)
        layout.addSpacing(22)

        self.sidebar_buttons = []

        def add_sidebar_button(label: str, page_key: str, icon) -> None:
            page_index = self.page_indexes[page_key]
            button = SidebarButton(
                label,
                icon,
                active=page_index == self.pages.currentIndex(),
            )
            button.clicked.connect(lambda _checked=False, index=page_index: self.switch_page(index))
            self.sidebar_buttons.append((button, page_index))
            layout.addWidget(button)

        role_name = self.user_data.get("role_name")
        if role_name == "Cashier":
            add_sidebar_button(
                "Cashier Dashboard",
                "cashier_dashboard",
                IconManager.icon("dashboard"),
            )
        elif role_name == "Manager":
            add_sidebar_button(
                "Manager Dashboard",
                "manager_dashboard",
                IconManager.icon("dashboard"),
            )
        elif role_name == "Admin":
            add_sidebar_button(
                "Admin Dashboard",
                "admin_dashboard",
                IconManager.icon("dashboard"),
            )

        self.terminal_button = SidebarButton(
            "POS Terminal",
            IconManager.icon("terminal"),
            active=False,
        )
        self.terminal_button.clicked.connect(
            lambda: self.switch_page(self.page_indexes["pos_terminal"])
        )
        self.sidebar_buttons.append((self.terminal_button, self.page_indexes["pos_terminal"]))

        layout.addWidget(self.terminal_button)

        if "products" in self.page_indexes:
            add_sidebar_button(
                "Product Management",
                "products",
                IconManager.icon("products"),
            )

        if role_name == "Manager":
            add_sidebar_button("Reports", "reports", IconManager.icon("reports"))
            add_sidebar_button("Registers", "registers", IconManager.icon("registers"))
            add_sidebar_button("Audit Logs", "audit_logs", IconManager.icon("audit_logs"))
        elif role_name == "Admin":
            add_sidebar_button("Users", "users", IconManager.icon("users"))
            add_sidebar_button("Registers", "registers", IconManager.icon("registers"))
            add_sidebar_button("Reports", "reports", IconManager.icon("reports"))
            add_sidebar_button("Audit Logs", "audit_logs", IconManager.icon("audit_logs"))
            add_sidebar_button("Settings", "settings", IconManager.icon("settings"))

        self.switch_page(self.pages.currentIndex())

        layout.addStretch(1)

        self.logout_button = QPushButton("Logout")
        self.logout_button.setObjectName("logoutButton")
        self.logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_button.setToolTip("Logout")
        self.logout_button.setProperty("expandedText", "Logout")
        self.logout_button.setProperty("collapsed", False)
        IconManager.apply_button(self.logout_button, "logout", IconManager.LIGHT)
        self.logout_button.clicked.connect(self.request_logout)
        layout.addWidget(self.logout_button)

        footer = QLabel("Developed by DevTeam2")
        footer.setObjectName("sidebarFooter")
        self.sidebar_expanded_widgets.append(footer)
        layout.addWidget(footer)

        return sidebar

    def create_sidebar_toggle_button(self) -> None:
        if self.central_container is None:
            return
        self.sidebar_toggle_button = QPushButton()
        self.sidebar_toggle_button.setObjectName("sidebarToggleButton")
        self.sidebar_toggle_button.setParent(self.central_container)
        self.sidebar_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle_button.setFixedSize(26, 48)
        self.sidebar_toggle_button.setToolTip("Collapse sidebar")
        self.sidebar_toggle_button.setIcon(IconManager.icon("sidebar_collapse"))
        self.sidebar_toggle_button.setIconSize(QSize(16, 16))
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_button.raise_()
        QTimer.singleShot(0, self.position_sidebar_toggle_button)

    def position_sidebar_toggle_button(self) -> None:
        if self.central_container is None or self.sidebar_toggle_button is None:
            return

        button_width = self.sidebar_toggle_button.width()
        button_height = self.sidebar_toggle_button.height()
        sidebar_width = 0 if self.sidebar_collapsed or self.sidebar_widget is None else self.sidebar_widget.width()
        x = max(0, sidebar_width - (button_width // 2))
        y = max((self.central_container.height() - button_height) // 2, 0)
        self.sidebar_toggle_button.move(x, y)
        self.sidebar_toggle_button.raise_()

    def toggle_sidebar(self) -> None:
        self.set_sidebar_collapsed(not self.sidebar_collapsed)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        if self.sidebar_widget is None or self.sidebar_layout is None:
            return

        self.sidebar_collapsed = collapsed
        self.sidebar_widget.set_collapsed(collapsed)

        if self.sidebar_toggle_button is not None:
            self.sidebar_toggle_button.setToolTip("Expand sidebar" if collapsed else "Collapse sidebar")
            self.sidebar_toggle_button.setIcon(
                IconManager.icon("sidebar_expand" if collapsed else "sidebar_collapse")
            )
        QTimer.singleShot(0, self.position_sidebar_toggle_button)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_sidebar_toggle_button()


    def switch_page(self, page_index: int) -> None:
        products_index = self.page_indexes.get("products")
        if page_index == products_index:
            self.ensure_product_management_page()

        self.pages.setCurrentIndex(page_index)
        for button, button_page_index in self.sidebar_buttons:
            is_active = button_page_index == page_index
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)

        if page_index == self.page_indexes.get("pos_terminal"):
            self.search_input.setFocus()
        elif page_index == products_index and self.product_management_page is not None:
            if not getattr(self.product_management_page, "products_loaded", False):
                self.product_management_page.load_products()

    def create_content_area(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)

        layout.addWidget(self.create_product_grid_panel(), 3)
        layout.addWidget(self.create_checkout_panel(), 2)
        return container

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = IconManager.label("POS Terminal", "terminal", "workspaceTitle", icon_size=20)

        cashier_info = QLabel(
            f"{self.user_data.get('full_name', 'Cashier')} | "
            f"{self.user_data.get('role_name', 'Cashier')} | Shift #{self.shift_id}"
        )
        cashier_info.setObjectName("cashierInfo")
        cashier_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(heading)
        layout.addStretch(1)
        layout.addWidget(cashier_info)
        return bar

    def create_product_grid_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("cardPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(3)

        title = IconManager.label("Products", "products", "panelTitle")
        subtitle = QLabel("Search or scan barcode to add items to cart")
        subtitle.setObjectName("panelSubtitle")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scan barcode or search product name...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setObjectName("posSearchInput")
        self.product_search_timer = QTimer(self)
        self.product_search_timer.setSingleShot(True)
        self.product_search_timer.setInterval(300)
        self.product_search_timer.timeout.connect(self.load_product_grid)
        self.search_input.textChanged.connect(self.schedule_product_grid_load)
        self.search_input.returnPressed.connect(self.handle_product_search)
        layout.addWidget(self.search_input)

        self.product_scroll_area = QScrollArea()
        self.product_scroll_area.setWidgetResizable(True)
        self.product_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.product_grid_container = QWidget()
        self.product_grid_layout = QGridLayout(self.product_grid_container)
        self.product_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.product_grid_layout.setHorizontalSpacing(14)
        self.product_grid_layout.setVerticalSpacing(14)
        self.product_scroll_area.setWidget(self.product_grid_container)

        layout.addWidget(self.product_scroll_area, 1)

        self.product_grid_status_label = QLabel("Click a product card or scan/type a product name, then press Enter")
        self.product_grid_status_label.setObjectName("statusHint")
        layout.addWidget(self.product_grid_status_label)

        self.load_product_grid()
        return panel

    def schedule_product_grid_load(self) -> None:
        self.product_search_timer.start()

    def clear_product_grid(self) -> None:
        while self.product_grid_layout.count():
            item = self.product_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def load_product_grid(self) -> None:
        keyword = self.search_input.text().strip()
        products = (
            db.search_products(keyword, limit=POS_PRODUCT_GRID_LIMIT + 1)
            if keyword
            else db.get_all_products(limit=POS_PRODUCT_GRID_LIMIT + 1)
        )
        has_more_products = len(products) > POS_PRODUCT_GRID_LIMIT
        products = products[:POS_PRODUCT_GRID_LIMIT]

        self.clear_product_grid()
        columns = 4
        for index, product in enumerate(products):
            card = self.create_product_card(product)
            self.product_grid_layout.addWidget(card, index // columns, index % columns)
        self.product_grid_layout.setRowStretch((len(products) // columns) + 1, 1)
        if has_more_products:
            self.product_grid_status_label.setText(
                f"Showing first {POS_PRODUCT_GRID_LIMIT} products. Search to narrow results."
            )
        else:
            self.product_grid_status_label.setText(
                "Click a product card or scan/type a product name, then press Enter"
            )

    def create_product_card(self, product) -> QFrame:
        card = QFrame()
        card.setObjectName("productCard")
        available_qty = float(product.get("stock_qty") or 0)
        is_out_of_stock = available_qty <= 0
        card.setProperty("outOfStock", is_out_of_stock)
        card.setCursor(
            Qt.CursorShape.ArrowCursor if is_out_of_stock else Qt.CursorShape.PointingHandCursor
        )
        card.setMinimumSize(150, 188)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)

        image_placeholder = QLabel("No Image")
        image_placeholder.setObjectName("productImagePlaceholder")
        image_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_placeholder.setMinimumHeight(76)
        image_path = str(product.get("image_path") or "")
        pixmap = ThumbnailCache.get(image_path, 150, 76, PROJECT_ROOT)
        if not pixmap.isNull():
            image_placeholder.setPixmap(pixmap)
            image_placeholder.setText("")

        name_label = QLabel(str(product["name"]))
        name_label.setObjectName("productName")
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        barcodes = list(product.get("barcodes") or [])
        barcode = self.format_product_barcodes(barcodes) or product["barcode"] or "No barcode"
        barcode_label = QLabel(f"Barcode: {barcode}")
        barcode_label.setObjectName("productBarcode")
        barcode_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        price_label = QLabel()
        price_label.setObjectName("productPrice")
        price_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        set_money_label(price_label, float(product["price"]), self.get_currency_symbol())

        stock_label = QLabel("Out of stock" if is_out_of_stock else f"Stock: {available_qty:g}")
        stock_label.setObjectName("outOfStockLabel" if is_out_of_stock else "productStock")
        stock_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(image_placeholder)
        layout.addWidget(name_label)
        layout.addWidget(barcode_label)
        layout.addWidget(price_label)
        layout.addWidget(stock_label)
        layout.addStretch(1)

        if not is_out_of_stock:
            card.mousePressEvent = lambda event, selected_product=product: self.add_product_to_cart(
                selected_product
            )
        return card

    def format_product_barcodes(self, barcodes: list[str]) -> str:
        if not barcodes:
            return ""
        if len(barcodes) == 1:
            return barcodes[0]
        return f"{barcodes[0]} + {len(barcodes) - 1} more"

    def create_checkout_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("checkoutPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(16)

        self.cart_count_label = QLabel("0 items")
        self.cart_count_label.setObjectName("panelSubtitle")
        self.cart_count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.cart_table = QTableWidget(0, 6)
        self.cart_table.setHorizontalHeaderLabels(["Barcode", "Name", "Qty", "Price", "Total", ""])
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setShowGrid(False)
        self.cart_table.setSortingEnabled(False)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.cart_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(58)
        self.cart_table.horizontalHeader().setStretchLastSection(False)
        self.cart_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.setColumnWidth(0, 110)
        self.cart_table.setColumnWidth(2, 54)
        self.cart_table.setColumnWidth(3, 88)
        self.cart_table.setColumnWidth(4, 94)
        self.cart_table.setColumnWidth(5, 34)
        self.cart_table.itemSelectionChanged.connect(self.sync_status)
        self.cart_table.itemChanged.connect(self.handle_cart_item_changed)
        self.cart_table.setObjectName("cartTable")
        self.cart_table.setMinimumHeight(300)
        self.cart_table.setMaximumHeight(430)
        layout.addWidget(self.cart_table, 1)

        totals_panel = QFrame()
        totals_panel.setObjectName("totalBlock")
        totals_layout = QVBoxLayout(totals_panel)
        totals_layout.setContentsMargins(16, 14, 16, 14)
        totals_layout.setSpacing(10)

        self.subtotal_value_label = QLabel()
        self.subtotal_value_label.setObjectName("amountValue")
        self.subtotal_value_label.setMinimumWidth(120)
        self.subtotal_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        set_money_label(self.subtotal_value_label, 0, self.get_currency_symbol())

        self.discount_input = QLineEdit("0.00")
        self.discount_input.setObjectName("discountInput")
        self.discount_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.discount_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))
        self.discount_input.textChanged.connect(self.refresh_total)

        self.total_value_label = QLabel()
        self.total_value_label.setObjectName("totalValue")
        self.total_value_label.setMinimumWidth(140)
        self.total_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        set_money_label(self.total_value_label, 0, self.get_currency_symbol())

        totals_layout.addLayout(self.create_amount_row("Subtotal", self.subtotal_value_label))
        totals_layout.addLayout(self.create_amount_row("Discount", self.discount_input))
        totals_layout.addLayout(self.create_amount_row("Grand Total", self.total_value_label))
        layout.addWidget(totals_panel)

        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(0, 2, 0, 0)
        action_layout.setSpacing(10)

        pay_cash_button = ActionButton("Pay", "primary")
        pay_cash_button.setObjectName("payButton")
        IconManager.apply_button(pay_cash_button, "payment", IconManager.LIGHT)
        split_payment_button = ActionButton("Split Payment", "warning")
        split_payment_button.setObjectName("splitButton")
        IconManager.apply_button(split_payment_button, "payment", IconManager.LIGHT)
        void_button = ActionButton("Cancel", "neutral")
        void_button.setObjectName("cancelButton")
        IconManager.apply_button(void_button, "cancel", IconManager.DARK)

        pay_cash_button.clicked.connect(self.handle_pay_cash)
        split_payment_button.clicked.connect(self.handle_split_payment)
        void_button.clicked.connect(self.handle_void_cancel)

        action_layout.addWidget(pay_cash_button)
        action_layout.addWidget(split_payment_button)
        action_layout.addWidget(void_button)

        layout.addLayout(action_layout)
        return panel

    def create_amount_row(self, label_text: str, value_widget: QWidget) -> QHBoxLayout:
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setObjectName("amountLabel")
        row_layout.addWidget(label)
        row_layout.addStretch(1)
        row_layout.addWidget(value_widget)
        return row_layout

    def create_shortcuts(self) -> None:
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.handle_void_cancel)

        refresh_shortcut = QShortcut(QKeySequence("Shift+F5"), self)
        refresh_shortcut.activated.connect(self.handle_reset_shortcut)

        focus_search_action = QAction(self)
        IconManager.apply_action(focus_search_action, "search")
        focus_search_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_search_action.triggered.connect(self.search_input.setFocus)
        self.addAction(focus_search_action)

    def handle_reset_shortcut(self) -> None:
        self.notify_app_data_changed()
        self.statusBar().showMessage("Reset successful", 2500)
        self.show_reset_toast("Reset successful")

    def show_reset_toast(self, message: str) -> None:
        if self.reset_toast is None:
            self.reset_toast = QLabel(self)
            self.reset_toast.setObjectName("resetToast")
            self.reset_toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.reset_toast_effect = QGraphicsOpacityEffect(self.reset_toast)
            self.reset_toast.setGraphicsEffect(self.reset_toast_effect)

        self.reset_toast.setText(message)
        self.reset_toast.adjustSize()
        toast_width = max(self.reset_toast.width() + 34, 180)
        toast_height = max(self.reset_toast.height() + 18, 42)
        self.reset_toast.resize(toast_width, toast_height)
        self.reset_toast.move(
            max(self.width() - toast_width - 28, 20),
            max(self.height() - toast_height - 58, 20),
        )
        self.reset_toast.raise_()
        self.reset_toast.show()

        if self.reset_toast_animation is not None:
            self.reset_toast_animation.stop()

        if self.reset_toast_effect is None:
            return

        self.reset_toast_effect.setOpacity(0.0)
        self.reset_toast_animation = QPropertyAnimation(self.reset_toast_effect, b"opacity", self)
        self.reset_toast_animation.setDuration(1700)
        self.reset_toast_animation.setKeyValueAt(0.0, 0.0)
        self.reset_toast_animation.setKeyValueAt(0.18, 1.0)
        self.reset_toast_animation.setKeyValueAt(0.78, 1.0)
        self.reset_toast_animation.setKeyValueAt(1.0, 0.0)
        self.reset_toast_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.reset_toast_animation.finished.connect(self.reset_toast.hide)
        self.reset_toast_animation.start()

    def request_logout(self) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        log_audit(int(self.user_data.get("id", 0)), "LOGOUT")
        clear_session()
        self.logout_requested = True
        self.close()

    def handle_product_search(self) -> None:
        self.product_search_timer.stop()
        keyword = self.search_input.text().strip()
        if not keyword:
            return

        product, matches = db.find_product_for_sale(keyword)
        if product is None:
            if matches:
                QMessageBox.warning(
                    self,
                    "Multiple Products Found",
                    "Multiple products match this search. Please type a more specific name or barcode.",
                )
            elif db.was_barcode_sold(keyword):
                QMessageBox.warning(
                    self,
                    "Out of Stock",
                    f"Barcode {keyword} has already been sold and is no longer available in inventory.",
                )
            else:
                QMessageBox.warning(self, "Product Not Found", "No product was found.")
            return

        self.add_product_to_cart(product)
        self.search_input.clear()
        self.search_input.setFocus()

    def add_product_to_cart(self, product) -> None:
        product_id = int(product["id"])
        scanned_barcode = product["barcode"] or product.get("primary_barcode") or ""
        quantity = 1.0
        if product["requires_weight"]:
            quantity, accepted = QInputDialog.getDouble(
                self,
                "Weighted Item",
                f"Enter weight/quantity for {product['name']}:",
                1.0,
                0.01,
                999999.0,
                3,
            )
            if not accepted:
                return

        current_cart_qty = self.get_cart_quantity_for_product(product_id)
        available_qty = db.get_available_stock(product_id)
        if available_qty <= 0:
            self.show_out_of_stock_warning(product["name"])
            return
        if current_cart_qty + quantity > available_qty:
            self.show_out_of_stock_warning(product["name"], available_qty)
            return

        for cart_item in self.cart_items:
            if cart_item.product_id == product_id:
                cart_item.qty += quantity
                self.populate_cart()
                self.statusBar().showMessage(f"Quantity increased: {cart_item.name}", 2500)
                return

        self.cart_items.append(
            CartItem(
                product_id=product_id,
                barcode=scanned_barcode,
                name=product["name"],
                qty=quantity,
                unit_price=float(product["price"]),
                requires_weight=bool(product["requires_weight"]),
            )
        )
        self.populate_cart()
        self.statusBar().showMessage(f"Added: {product['name']}", 2500)

    def populate_cart(self) -> None:
        self.cart_table_updating = True
        self.cart_table.setRowCount(len(self.cart_items))
        for row, item in enumerate(self.cart_items):
            values = [
                item.barcode,
                item.name,
                f"{item.qty:g}",
                item.unit_price,
                item.subtotal,
            ]
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                if column == 3:
                    set_money_table_item(table_item, item.unit_price, self.get_currency_symbol())
                elif column == 4:
                    set_money_table_item(table_item, item.subtotal, self.get_currency_symbol())
                table_item.setData(Qt.ItemDataRole.UserRole, item.product_id)
                table_item.setData(Qt.ItemDataRole.UserRole + 1, item.barcode)
                if column in (0, 1):
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                elif column >= 3:
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column != 2:
                    table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.cart_table.setItem(row, column, table_item)

            delete_button = QPushButton()
            delete_button.setObjectName("tableDeleteIconButton")
            delete_button.setToolTip("Remove item")
            delete_button.setFixedSize(28, 28)
            IconManager.apply_button(delete_button, "delete", "#DC2626", size=16)
            delete_button.clicked.connect(
                lambda _checked=False, product_id=item.product_id: self.remove_cart_item(product_id)
            )
            self.cart_table.setCellWidget(row, 5, delete_button)

        self.cart_table_updating = False
        if hasattr(self, "cart_count_label"):
            item_count = len(self.cart_items)
            self.cart_count_label.setText(f"{item_count} item" if item_count == 1 else f"{item_count} items")
        self.refresh_total()
        if self.cart_table.rowCount() > 0:
            self.cart_table.scrollToBottom()

    def handle_cart_item_changed(self, table_item: QTableWidgetItem) -> None:
        if self.cart_table_updating or table_item.column() != 2:
            return

        product_id = table_item.data(Qt.ItemDataRole.UserRole)
        try:
            new_qty = float(table_item.text().strip())
        except ValueError:
            self.populate_cart()
            QMessageBox.warning(self, "Invalid Quantity", "Quantity must be a valid number.")
            return

        if new_qty <= 0:
            self.remove_cart_item(product_id)
            return

        available_qty = db.get_available_stock(int(product_id))
        if new_qty > available_qty:
            self.populate_cart()
            self.show_out_of_stock_warning(
                self.get_cart_item_name(int(product_id)) or f"Product #{product_id}",
                available_qty,
            )
            return

        for item in self.cart_items:
            if item.product_id == product_id:
                item.qty = new_qty
                break
        self.populate_cart()

    def remove_cart_item(self, product_id: int) -> None:
        self.cart_items = [
            item
            for item in self.cart_items
            if item.product_id != product_id
        ]
        self.populate_cart()

    def get_cart_quantity_for_product(self, product_id: int) -> float:
        return sum(item.qty for item in self.cart_items if item.product_id == product_id)

    def get_cart_item_name(self, product_id: int) -> str | None:
        for item in self.cart_items:
            if item.product_id == product_id:
                return item.name
        return None

    def show_out_of_stock_warning(self, product_name: str, available_qty: float = 0) -> None:
        if available_qty > 0:
            message = (
                f"{product_name} does not have enough stock.\n"
                f"Available now: {available_qty:g}"
            )
        else:
            message = f"{product_name} is out of stock and cannot be added to this sale."
        QMessageBox.warning(self, "Out of Stock", message)

    def ensure_cart_in_stock(self) -> bool:
        for item in self.cart_items:
            available_qty = db.get_available_stock(item.product_id)
            if available_qty <= 0 or item.qty > available_qty:
                self.show_out_of_stock_warning(item.name, available_qty)
                return False
        return True

    def refresh_total(self) -> None:
        subtotal = self.get_cart_subtotal()
        discount = min(self.get_discount_amount(), subtotal)
        grand_total = max(subtotal - discount, 0)

        set_money_label(self.subtotal_value_label, subtotal, self.get_currency_symbol())
        set_money_label(self.total_value_label, grand_total, self.get_currency_symbol())

    def sync_status(self) -> None:
        selected = self.cart_table.currentRow()
        if selected < 0 or selected >= len(self.cart_items):
            return
        item = self.cart_items[selected]
        self.statusBar().showMessage(f"Selected: {item.name} x{item.qty}", 2500)

    def handle_keypad_press(self, value: str) -> None:
        if not hasattr(self, "tender_input"):
            return
        if value == "Backspace":
            self.tender_input.backspace()
            return
        self.tender_input.insert(value)

    def handle_pay_cash(self) -> None:
        total_amount = self.get_cart_total()
        if total_amount <= 0:
            QMessageBox.warning(self, "Empty Cart", "Please add products before payment.")
            return
        if not self.ensure_cart_in_stock():
            return

        self.open_payment_dialog(total_amount)

    def finalize_successful_payment(self, payment_result: dict[str, object]) -> None:
        payment_method = str(payment_result["payment_method"])
        normalized_payment_method = payment_method.strip().replace("_", " ").lower()
        success_message = "Payment successful."
        if normalized_payment_method == "cash":
            success_message += f"\nChange: {self.format_money(float(payment_result['change_amount']))}"
        else:
            success_message += f"\nMethod: {payment_method}"

        QMessageBox.information(
            self,
            "Payment Successful",
            success_message,
        )
        self.notify_app_data_changed()
        receipt_text = self.build_receipt_text(
            sale_items=payment_result["sale_items"],
            total_amount=float(payment_result["total_amount"]),
            tendered_amount=float(payment_result["tendered_amount"]),
            change_amount=float(payment_result["change_amount"]),
            payment_method=payment_method,
            order_id=int(payment_result["sale_id"]) if payment_result.get("sale_id") else None,
            cashier_name=str(self.user_data.get("full_name") or self.user_data.get("username") or ""),
            note=str(payment_result.get("note") or ""),
            payments=payment_result.get("payments") if isinstance(payment_result.get("payments"), list) else None,
        )
        self.show_receipt_preview(receipt_text)
        self.clear_current_sale()

    def open_payment_dialog(self, total_amount: float) -> None:
        payment_settings = self.get_payment_settings()
        bank_transfer_enabled = bool(payment_settings["enable_bank_transfer"])

        dialog = QDialog(self)
        dialog.setWindowTitle("Payment")
        dialog.setModal(True)
        dialog.resize(820, 640)

        root_layout = QVBoxLayout(dialog)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(20)

        dialog_header = QVBoxLayout()
        dialog_header.setContentsMargins(0, 0, 0, 0)
        dialog_header.setSpacing(4)

        dialog_title = IconManager.label("Payment", "payment", "paymentDialogTitle", icon_size=20)
        dialog_subtitle = QLabel("Review tendered amount, change, and payment method")
        dialog_subtitle.setObjectName("paymentDialogSubtitle")

        dialog_header.addWidget(dialog_title)
        dialog_header.addWidget(dialog_subtitle)
        root_layout.addLayout(dialog_header)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        root_layout.addLayout(content_layout, 1)

        left_panel = QFrame()
        left_panel.setObjectName("paymentDialogPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(13)

        grand_total_title = QLabel("Total Due")
        grand_total_title.setObjectName("paymentFieldLabel")
        grand_total_value = QLabel()
        grand_total_value.setObjectName("paymentGrandTotal")
        set_money_label(grand_total_value, total_amount, self.get_currency_symbol())

        amount_tendered_input = QLineEdit()
        amount_tendered_input.setPlaceholderText("Amount Tendered")
        amount_tendered_input.setObjectName("amountTenderedInput")
        amount_tendered_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        amount_tendered_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        change_value = QLabel()
        change_value.setObjectName("paymentChangeValue")
        set_money_label(change_value, 0, self.get_currency_symbol())

        note_input = QLineEdit()
        note_input.setPlaceholderText("Note")

        amount_label = QLabel("Amount Tendered")
        amount_label.setObjectName("paymentFieldLabel")
        change_label = QLabel("Change")
        change_label.setObjectName("paymentFieldLabel")
        note_label = QLabel("Note")
        note_label.setObjectName("paymentFieldLabel")

        left_layout.addWidget(grand_total_title)
        left_layout.addWidget(grand_total_value)
        left_layout.addSpacing(4)
        left_layout.addWidget(amount_label)
        left_layout.addWidget(amount_tendered_input)
        left_layout.addWidget(change_label)
        left_layout.addWidget(change_value)
        left_layout.addWidget(note_label)
        left_layout.addWidget(note_input)
        left_layout.addStretch(1)

        right_panel = QFrame()
        right_panel.setObjectName("paymentDialogPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        method_title = QLabel("Payment Method")
        method_title.setObjectName("paymentFieldLabel")
        cash_radio = QRadioButton("Cash")
        cash_radio.setIcon(IconManager.icon("cash"))
        cash_radio.setIconSize(QSize(18, 18))
        cash_radio.setChecked(True)
        bank_radio = QRadioButton("Bank Transfer")
        bank_radio.setIcon(IconManager.icon("payment"))
        bank_radio.setIconSize(QSize(18, 18))
        bank_radio.setEnabled(bank_transfer_enabled)
        if not bank_transfer_enabled:
            bank_radio.setToolTip("Enable Bank Transfer in Settings first.")

        right_layout.addWidget(method_title)
        right_layout.addWidget(cash_radio)
        right_layout.addWidget(bank_radio)

        bank_qr_panel = self.create_bank_qr_panel(payment_settings, PAYMENT_QR_DISPLAY_SIZE)
        bank_qr_panel.setVisible(False)
        right_layout.addWidget(bank_qr_panel)
        right_layout.addStretch(1)

        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("neutralDialogButton")
        IconManager.apply_button(cancel_button, "cancel", IconManager.DARK)
        confirm_button = QPushButton("CONFIRM")
        confirm_button.setObjectName("primaryDialogButton")
        IconManager.apply_button(confirm_button, "confirm", IconManager.LIGHT)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        root_layout.addLayout(button_layout)

        def get_tendered_amount() -> float | None:
            try:
                return self.parse_money(amount_tendered_input.text())
            except ValueError:
                QMessageBox.warning(
                    dialog,
                    "Invalid Tendered Amount",
                    "Please enter a valid tendered amount.",
                )
                return None

        def update_change() -> None:
            try:
                tendered_amount = self.parse_money(amount_tendered_input.text() or "0")
            except ValueError:
                set_money_label(change_value, 0, self.get_currency_symbol())
                return
            set_money_label(
                change_value,
                max(tendered_amount - total_amount, 0),
                self.get_currency_symbol(),
            )

        def toggle_bank_transfer_ui(checked: bool) -> None:
            bank_qr_panel.setVisible(checked and bank_transfer_enabled)
            if checked and bank_transfer_enabled:
                amount_tendered_input.setText(f"{total_amount:.2f}")

        payment_result: dict[str, object] | None = None

        def confirm_payment() -> None:
            nonlocal payment_result
            if bank_radio.isChecked() and not bank_transfer_enabled:
                QMessageBox.warning(
                    dialog,
                    "Bank Transfer Disabled",
                    "Please enable Bank Transfer in Settings before using this payment method.",
                )
                return

            tendered_amount = get_tendered_amount()
            if tendered_amount is None:
                return
            if tendered_amount < total_amount:
                QMessageBox.warning(
                    dialog,
                    "Insufficient Payment",
                    "Tendered amount is less than the grand total.",
                )
                return

            payment_method = "Cash" if cash_radio.isChecked() else "Bank Transfer"
            change_amount = tendered_amount - total_amount
            sale_items = self.get_sale_items_from_cart_table()
            note_text = note_input.text().strip()
            payment_rows = [{"method": payment_method, "amount": total_amount}]

            try:
                if not self.ensure_cart_in_stock():
                    return
                sale_id = db.create_sale(
                    total_amount,
                    payment_method,
                    sale_items,
                    user_id=int(self.user_data.get("id", 0)),
                    register_id=self.register_id,
                    shift_id=self.shift_id,
                    tendered_amount=tendered_amount,
                    change_amount=change_amount,
                    note=note_text,
                    payments=payment_rows,
                )
                if payment_method == "Cash":
                    add_cash_movement(
                        self.shift_id,
                        int(self.user_data.get("id", 0)),
                        "sale",
                        total_amount,
                        f"Cash sale #{sale_id}",
                    )
                log_audit(
                    self.user_data["id"],
                    "CREATE_SALE",
                    "sales",
                    sale_id,
                    None,
                    f"total: {total_amount:.2f}",
                )
            except ValueError as error:
                QMessageBox.warning(dialog, "Inventory Error", str(error))
                return
            except Exception as error:
                QMessageBox.warning(dialog, "Database Error", f"Could not save sale: {error}")
                return

            payment_result = {
                "sale_id": sale_id,
                "sale_items": sale_items,
                "total_amount": total_amount,
                "tendered_amount": tendered_amount,
                "change_amount": change_amount,
                "payment_method": payment_method,
                "note": note_text,
                "payments": payment_rows,
            }
            dialog.accept()

        amount_tendered_input.textChanged.connect(update_change)
        bank_radio.toggled.connect(toggle_bank_transfer_ui)
        cancel_button.clicked.connect(dialog.reject)
        confirm_button.clicked.connect(confirm_payment)
        amount_tendered_input.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted and payment_result is not None:
            self.finalize_successful_payment(payment_result)

    def handle_split_payment(self) -> None:
        total_amount = self.get_cart_total()
        if total_amount <= 0:
            QMessageBox.warning(self, "Empty Cart", "Please add products before payment.")
            return
        if not self.ensure_cart_in_stock():
            return

        payment_settings = self.get_payment_settings()
        bank_transfer_enabled = bool(payment_settings["enable_bank_transfer"])

        dialog = QDialog(self)
        dialog.setWindowTitle("Split Payment")
        dialog.setModal(True)
        dialog.setMinimumWidth(720)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        total_label = QLabel()
        total_label.setObjectName("dialogTotalLabel")
        set_money_label(total_label, total_amount, self.get_currency_symbol(), "Total Amount: ")
        layout.addWidget(total_label)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        left_panel = QFrame()
        left_panel.setObjectName("paymentDialogPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)

        cash_input = QLineEdit()
        cash_input.setPlaceholderText("0.00")
        cash_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        transfer_input = QLineEdit()
        transfer_input.setPlaceholderText("0.00")
        transfer_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        note_input = QLineEdit()
        note_input.setPlaceholderText("Note")

        form_layout.addRow("Cash", cash_input)
        form_layout.addRow("Bank Transfer", transfer_input)
        form_layout.addRow("Note", note_input)

        left_layout.addLayout(form_layout)
        left_layout.addStretch(1)

        bank_qr_panel = self.create_bank_qr_panel(
            payment_settings,
            SPLIT_PAYMENT_QR_DISPLAY_SIZE,
            "Bank Transfer QR",
        )

        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(bank_qr_panel, 0)
        layout.addLayout(content_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("neutralDialogButton")
        IconManager.apply_button(cancel_button, "cancel", IconManager.DARK)
        cancel_button.clicked.connect(dialog.reject)

        confirm_button = QPushButton("Confirm")
        confirm_button.setObjectName("primaryDialogButton")
        IconManager.apply_button(confirm_button, "confirm", IconManager.LIGHT)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        layout.addLayout(button_layout)

        payment_result: dict[str, object] | None = None

        def confirm_split_payment() -> None:
            nonlocal payment_result
            try:
                cash_amount = self.parse_money(cash_input.text() or "0")
                transfer_amount = self.parse_money(transfer_input.text() or "0")
            except ValueError:
                QMessageBox.warning(dialog, "Invalid Amount", "Please enter valid payment amounts.")
                return

            if transfer_amount > 0 and not bank_transfer_enabled:
                QMessageBox.warning(
                    dialog,
                    "Bank Transfer Disabled",
                    "Please enable Bank Transfer in Settings before using a bank transfer split amount.",
                )
                return

            tendered_amount = cash_amount + transfer_amount
            if tendered_amount < total_amount:
                QMessageBox.warning(
                    dialog,
                    "Insufficient Payment",
                    "Cash plus Bank Transfer amount is less than the total amount.",
                )
                return

            change_amount = tendered_amount - total_amount
            sale_items = self.get_sale_items_from_cart_table()
            note_text = note_input.text().strip()
            payment_rows = []
            if cash_amount > 0:
                payment_rows.append({"method": "Cash", "amount": cash_amount})
            if transfer_amount > 0:
                payment_rows.append({"method": "Bank Transfer", "amount": transfer_amount})

            try:
                if not self.ensure_cart_in_stock():
                    return
                sale_id = db.create_sale(
                    total_amount,
                    "Split",
                    sale_items,
                    user_id=int(self.user_data.get("id", 0)),
                    register_id=self.register_id,
                    shift_id=self.shift_id,
                    tendered_amount=tendered_amount,
                    change_amount=change_amount,
                    note=note_text,
                    payments=payment_rows,
                )
                if cash_amount > 0:
                    add_cash_movement(
                        self.shift_id,
                        int(self.user_data.get("id", 0)),
                        "sale",
                        min(cash_amount, total_amount),
                        f"Split sale #{sale_id}",
                    )
                log_audit(self.user_data["id"], "CREATE_SALE", "sales", sale_id, None, f"total: {total_amount:.2f}")
            except ValueError as error:
                QMessageBox.warning(dialog, "Inventory Error", str(error))
                return
            except Exception as error:
                QMessageBox.warning(dialog, "Database Error", f"Could not save sale: {error}")
                return

            payment_result = {
                "sale_id": sale_id,
                "sale_items": sale_items,
                "total_amount": total_amount,
                "tendered_amount": tendered_amount,
                "change_amount": change_amount,
                "payment_method": "Split",
                "note": note_text,
                "payments": payment_rows,
            }
            dialog.accept()

        confirm_button.clicked.connect(confirm_split_payment)
        if dialog.exec() == QDialog.DialogCode.Accepted and payment_result is not None:
            self.finalize_successful_payment(payment_result)

    def handle_void_cancel(self) -> None:
        if not self.cart_items and self.get_discount_amount() == 0:
            self.search_input.clear()
            self.search_input.setFocus()
            return

        reply = QMessageBox.question(
            self,
            "Confirm Void",
            "Are you sure you want to void this transaction?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.clear_current_sale()
        self.statusBar().showMessage("Transaction voided", 2500)

    def parse_money(self, value: str) -> float:
        return parse_money_text(value, self.get_currency_symbol())

    def get_cart_subtotal(self) -> float:
        return sum(item.subtotal for item in self.cart_items)

    def get_discount_amount(self) -> float:
        if not hasattr(self, "discount_input"):
            return 0.0
        try:
            return self.parse_money(self.discount_input.text() or "0")
        except ValueError:
            return 0.0

    def get_cart_total(self) -> float:
        subtotal = self.get_cart_subtotal()
        return max(subtotal - min(self.get_discount_amount(), subtotal), 0)

    def get_sale_items_from_cart_table(self) -> list[dict[str, object]]:
        return [
            {
                "barcode": item.barcode,
                "product_id": item.product_id,
                "name": item.name,
                "qty": item.qty,
                "price": item.unit_price,
                "subtotal": item.subtotal,
            }
            for item in self.cart_items
        ]

    def build_receipt_text(
        self,
        sale_items: list[dict[str, object]],
        total_amount: float,
        tendered_amount: float,
        change_amount: float,
        payment_method: str,
        order_id: int | None = None,
        cashier_name: str = "",
        note: str = "",
        payments: list[dict[str, object]] | None = None,
    ) -> str:
        settings = self.get_receipt_settings()
        currency_symbol = settings["currency_symbol"]
        line_width = 36
        divider = "=" * line_width
        thin_divider = "-" * line_width
        normalized_payment_method = payment_method.strip().replace("_", " ").lower()
        if normalized_payment_method == "cash":
            payment_label = "Cash"
        elif normalized_payment_method == "bank transfer":
            payment_label = "Bank Transfer"
        elif normalized_payment_method == "split":
            payment_label = "Split Payment"
        else:
            payment_label = payment_method

        def center_text(value: str) -> str:
            return value.strip().center(line_width)

        def center_wrapped(value: str, uppercase: bool = False) -> list[str]:
            rendered_lines: list[str] = []
            normalized_text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
            for raw_line in normalized_text.split("\n"):
                clean_line = " ".join(raw_line.split())
                if not clean_line:
                    continue
                if uppercase:
                    clean_line = clean_line.upper()
                chunks = wrap(clean_line, width=line_width, break_long_words=True) or [clean_line]
                rendered_lines.extend(chunk.center(line_width) for chunk in chunks)
            return rendered_lines

        def amount_row(label: str, amount: float) -> str:
            value = self.format_money(amount, currency_symbol)
            clean_label = str(label)[:16]
            return f"{clean_label:<16}{value:>{line_width - 16}}"

        def info_row(label: str, value: str | int) -> str:
            text = str(value)
            return f"{label:<9}{text:>{line_width - 9}}"

        def labeled_wrapped(label: str, value: str) -> list[str]:
            clean_value = " ".join(str(value or "").split())
            if not clean_value:
                return []
            prefix = f"{label}: "
            available_width = max(line_width - len(prefix), 8)
            chunks = wrap(clean_value, width=available_width, break_long_words=True)
            rendered_lines: list[str] = []
            for index, chunk in enumerate(chunks):
                if index == 0:
                    rendered_lines.append(f"{prefix}{chunk}")
                else:
                    rendered_lines.append(f"{' ' * len(prefix)}{chunk}")
            return rendered_lines

        def compact_name(value: str) -> str:
            return " ".join(value.split())

        lines: list[str] = []

        if settings["store_name"]:
            lines.extend(center_wrapped(settings["store_name"], uppercase=True))

        if settings["store_address"]:
            lines.extend(center_wrapped(settings["store_address"]))
        if settings["store_phone"]:
            lines.extend(center_wrapped(f"Tel: {settings['store_phone']}"))
        if settings["receipt_header"]:
            lines.extend(center_wrapped(settings["receipt_header"]))
        if lines:
            lines.append(divider)

        lines.extend(
            [
                center_text("SALES RECEIPT"),
                thin_divider,
            ]
        )

        if order_id is not None:
            lines.append(info_row("Order", f"#{order_id}"))
        if cashier_name:
            lines.append(info_row("Cashier", cashier_name[: line_width - 9]))
        lines.append(info_row("Date", datetime.now().strftime("%Y-%m-%d %H:%M")))
        lines.append(info_row("Payment", payment_label))
        if note:
            lines.extend(labeled_wrapped("Note", note))
        lines.append(thin_divider)

        for item in sale_items:
            name = compact_name(str(item["name"]))
            qty = float(item["qty"])
            price = float(item["price"])
            subtotal = float(item["subtotal"])

            while name:
                lines.append(name[:line_width].rstrip())
                name = name[line_width:].lstrip()

            qty_price = f"{qty:g} x {self.format_money(price, currency_symbol)}"
            subtotal_text = self.format_money(subtotal, currency_symbol)
            lines.append(f"  {qty_price:<17}{subtotal_text:>{line_width - 19}}")

        lines.extend(
            [
                thin_divider,
                amount_row("TOTAL", total_amount),
            ]
        )

        payment_rows = payments or []
        visible_payment_rows = []
        for payment in payment_rows:
            try:
                payment_amount = float(payment.get("amount") or 0)  # type: ignore[union-attr]
            except (TypeError, ValueError, AttributeError):
                continue
            if payment_amount <= 0:
                continue
            try:
                payment_method_label = str(payment.get("method") or "Payment")  # type: ignore[union-attr]
            except AttributeError:
                payment_method_label = "Payment"
            visible_payment_rows.append((payment_method_label, payment_amount))

        if visible_payment_rows and normalized_payment_method != "cash":
            for payment_method_label, payment_amount in visible_payment_rows:
                lines.append(amount_row(payment_method_label, payment_amount))

        if normalized_payment_method in {"cash", "split"}:
            lines.append(amount_row("Tendered", tendered_amount))
            lines.append(amount_row("Change", change_amount))

        lines.append(divider)

        if settings["receipt_footer"]:
            lines.extend(center_wrapped(settings["receipt_footer"]))

        return "\n".join(lines)

    def show_receipt_preview(self, receipt_text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Receipt Preview")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        preview_title = QLabel("Receipt Preview")
        preview_title.setObjectName("receiptPreviewTitle")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_title)

        receipt_font = QFont("Courier New", 9)
        receipt_font.setStyleHint(QFont.StyleHint.Monospace)
        receipt_font.setFixedPitch(True)

        receipt_lines = receipt_text.splitlines() or [""]
        font_metrics = QFontMetrics(receipt_font)
        text_width = max(font_metrics.horizontalAdvance(line) for line in receipt_lines)
        text_height = font_metrics.lineSpacing() * len(receipt_lines) + (font_metrics.lineSpacing() * 2)

        paper_padding_x = 18
        paper_padding_y = 16
        paper_width = max(286, text_width + paper_padding_x * 2)
        paper_height = text_height + paper_padding_y * 2

        receipt_paper = QFrame()
        receipt_paper.setObjectName("receiptPreviewPaper")
        receipt_paper.setFixedWidth(paper_width)
        receipt_paper.setMinimumHeight(paper_height)

        paper_layout = QVBoxLayout(receipt_paper)
        paper_layout.setContentsMargins(paper_padding_x, paper_padding_y, paper_padding_x, paper_padding_y)
        paper_layout.setSpacing(0)

        receipt_label = QLabel(receipt_text)
        receipt_label.setObjectName("receiptPreviewText")
        receipt_label.setFont(receipt_font)
        receipt_label.setTextFormat(Qt.TextFormat.PlainText)
        receipt_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        receipt_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        receipt_label.setWordWrap(False)
        receipt_label.setMinimumWidth(text_width)
        receipt_label.setMinimumHeight(text_height)
        receipt_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        paper_layout.addWidget(receipt_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(receipt_paper, 0, Qt.AlignmentFlag.AlignCenter)

        close_button = QPushButton("Close")
        close_button.setObjectName("primaryDialogButton")
        IconManager.apply_button(close_button, "close", IconManager.LIGHT)
        close_button.clicked.connect(dialog.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.setStyleSheet(
            f"""
            QDialog {{
                background: #EEF2F6;
            }}

            #receiptPreviewTitle {{
                background: transparent;
                color: {TEXT_DARK};
                font-size: 16px;
                font-weight: 800;
            }}

            #receiptPreviewPaper {{
                background: #FFFFFF;
                border: 1px solid {BORDER};
                border-radius: 3px;
            }}

            #receiptPreviewText {{
                background: transparent;
                color: #111827;
            }}
            """
        )

        dialog.adjustSize()
        dialog.setFixedSize(dialog.sizeHint())
        dialog.exec()

    def clear_current_sale(self) -> None:
        self.cart_items.clear()
        self.populate_cart()
        if hasattr(self, "discount_input"):
            self.discount_input.setText("0.00")
        self.search_input.clear()
        self.search_input.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()


def build_stylesheet() -> str:
    return f"""
    * {{
        color: {TEXT_DARK};
        font-family: "Segoe UI";
        font-size: 13px;
    }}

    QMainWindow, QWidget {{
        background: {WINDOW_BG};
    }}

    QLabel {{
        background: transparent;
    }}

    QStatusBar {{
        background: #FFFFFF;
        border-top: 1px solid {BORDER};
        color: {TEXT_MUTED};
    }}

    #sidebar {{
        background: #FFFFFF;
        border-right: 1px solid {BORDER};
    }}

    #appTitle {{
        color: {TEXT_DARK};
        font-size: 22px;
        font-weight: 700;
    }}

    #appSubtitle, #sidebarFooter {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #sidebarBrandText {{
        background: transparent;
    }}

    #sidebarToggleButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 13px;
        min-height: 48px;
        max-height: 48px;
        min-width: 26px;
        max-width: 26px;
        padding: 0;
    }}

    #sidebarToggleButton:hover {{
        background: #F3F7FD;
        border-color: rgba(37, 99, 235, 0.35);
    }}

    #workspaceTitle {{
        font-size: 20px;
        font-weight: 700;
    }}

    #cashierInfo {{
        color: {TEXT_MUTED};
        font-size: 13px;
        font-weight: 600;
    }}

    SidebarButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 12px 14px;
        text-align: left;
    }}

    SidebarButton:hover {{
        background: #F3F7FD;
    }}

    SidebarButton[active="true"] {{
        background: rgba(37, 99, 235, 0.12);
        border-color: rgba(37, 99, 235, 0.24);
        color: {ACCENT_BLUE};
    }}

    SidebarButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton {{
        background: #DC2626;
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
        text-align: left;
    }}

    #logoutButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton:hover {{
        background: #B91C1C;
    }}

    #logoutButton:pressed {{
        background: #991B1B;
    }}

    #cardPanel, #checkoutPanel {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #panelTitle {{
        color: {TEXT_DARK};
        font-size: 20px;
        font-weight: 800;
    }}

    #panelSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 600;
    }}

    #productCard {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #productCard:hover {{
        border-color: {ACCENT_BLUE};
        background: #F8FBFF;
    }}

    #productCard[outOfStock="true"] {{
        background: #F8FAFC;
        border-color: #CBD5E1;
    }}

    #productImagePlaceholder {{
        background: #F8FAFC;
        border: 1px solid {BORDER};
        border-radius: 10px;
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #productName {{
        color: {TEXT_DARK};
        font-size: 13px;
        font-weight: 800;
    }}

    #productBarcode {{
        color: {TEXT_MUTED};
        font-size: 11px;
        font-weight: 600;
    }}

    #productPrice {{
        color: {TEXT_DARK};
        font-size: 16px;
        font-weight: 800;
    }}

    #productStock {{
        color: {ACCENT_GREEN};
        font-size: 12px;
        font-weight: 800;
    }}

    #outOfStockLabel {{
        color: #DC2626;
        font-size: 12px;
        font-weight: 800;
    }}

    #dashboardCard {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #dashboardCardTitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #dashboardCardValue {{
        color: {TEXT_DARK};
        font-size: 26px;
        font-weight: 800;
    }}

    #dashboardCardSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #dashboardActionButton {{
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 16px;
    }}

    #dashboardActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
    }}

    #dashboardActionButton[role="secondary"] {{
        background: {ACCENT_GREEN};
    }}

    QLineEdit {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px 12px;
        selection-background-color: {ACCENT_BLUE};
        selection-color: #FFFFFF;
    }}

    QLineEdit:focus {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QTableWidget {{
        alternate-background-color: #FAFBFD;
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: rgba(37, 99, 235, 0.16);
        selection-color: {TEXT_DARK};
    }}

    QHeaderView::section {{
        background: {PANEL_BG};
        border: none;
        border-bottom: 1px solid {BORDER};
        color: {TEXT_DARK};
        font-weight: 700;
        padding: 12px 10px;
    }}

    QTableWidget::item {{
        border-bottom: 1px solid #EFF3F7;
        padding: 8px 10px;
    }}

    QScrollBar:vertical {{
        background: #F3F7FD;
        border: none;
        border-left: 1px solid {BORDER};
        width: 12px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: #C1CDDA;
        border-radius: 5px;
        min-height: 32px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #9AA8B8;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    #statusHint {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #resetToast {{
        background: rgba(15, 118, 110, 0.96);
        border-radius: 10px;
        color: #FFFFFF;
        font-size: 13px;
        font-weight: 800;
        padding: 10px 16px;
    }}

    #totalBlock {{
        background: {PANEL_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #sectionLabel {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
    }}

    #totalValue {{
        color: {TEXT_DARK};
        font-size: 34px;
        font-weight: 800;
    }}

    #amountLabel {{
        color: {TEXT_MUTED};
        font-size: 13px;
        font-weight: 700;
    }}

    #amountValue {{
        color: {TEXT_DARK};
        font-size: 15px;
        font-weight: 800;
    }}

    #discountInput {{
        max-width: 110px;
        padding: 7px 9px;
    }}

    KeypadButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 15px;
        font-weight: 700;
    }}

    KeypadButton:hover {{
        background: #F7FAFD;
        border-color: #C1CDDA;
    }}

    KeypadButton:pressed {{
        background: #EAF4FE;
        border-color: {ACCENT_BLUE};
    }}

    ActionButton {{
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
    }}

    ActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
        color: #FFFFFF;
    }}

    ActionButton[role="warning"] {{
        background: {ACCENT_ORANGE};
        color: #FFFFFF;
    }}

    ActionButton[role="neutral"] {{
        background: #E0E0E0;
        color: {TEXT_DARK};
    }}

    #payButton {{
        min-height: 52px;
        font-size: 15px;
    }}

    #splitButton, #cancelButton {{
        min-height: 48px;
    }}
    
    #tableDeleteIconButton {{
        background: transparent;
        border: none;
        color: #DC2626;
        font-size: 15px;
        font-weight: 900;
        padding: 0;
        margin-left: -12px;
        margin-top: 5px;
    }}

    #tableDeleteIconButton:hover {{
        background: #FEF2F2;
        border-radius: 14px;
        color: #B91C1C;
    }}

    #dialogTotalLabel {{
        color: {TEXT_DARK};
        font-size: 16px;
        font-weight: 700;
    }}

    #paymentDialogPanel {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}

    #paymentDialogTitle {{
        color: {TEXT_DARK};
        font-size: 22px;
        font-weight: 800;
    }}

    #paymentDialogSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 600;
    }}

    #paymentFieldLabel {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }}

    #paymentGrandTotal {{
        color: {TEXT_DARK};
        font-size: 32px;
        font-weight: 800;
    }}

    #amountTenderedInput {{
        font-size: 22px;
        font-weight: 800;
        padding: 14px;
    }}

    #paymentChangeValue {{
        color: {ACCENT_BLUE};
        font-size: 26px;
        font-weight: 800;
    }}

    #paymentQrPanel {{
        background: #F8FAFC;
        border: 1px dashed {BORDER};
        border-radius: 12px;
    }}

    #paymentQrPreview {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #paymentQrDetails {{
        color: {TEXT_DARK};
        font-size: 12px;
        font-weight: 700;
    }}

    QRadioButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
        font-weight: 700;
        padding: 14px;
    }}

    QRadioButton:checked {{
        border-color: {ACCENT_BLUE};
        color: {ACCENT_BLUE};
    }}

    #primaryDialogButton {{
        background: {ACCENT_BLUE};
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-weight: 700;
        min-width: 140px;
        padding: 11px 18px;
    }}

    #neutralDialogButton {{
        background: #E5E7EB;
        border: none;
        border-radius: 8px;
        color: {TEXT_DARK};
        font-weight: 700;
        min-width: 120px;
        padding: 11px 18px;
    }}
    """


def configure_app_font(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet() + MODERN_WIDGET_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))
