from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QDoubleValidator, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database import db
from product_management.product_management_window import ProductManagementWindow

# Admin imports
from admin.admin_dashboard_window import create_admin_dashboard
from admin.user_management_window import create_user_management
from admin.register_management_window import create_register_management
from admin.reports_window import create_reports
from admin.audit_logs_window import create_audit_logs
from admin.settings_window import create_settings

from login import add_cash_movement, has_permission, log_audit, open_cash_shift


ACCENT_BLUE = "#2563EB"
ACCENT_GREEN = "#0F766E"
ACCENT_ORANGE = "#F97316"
TEXT_DARK = "#1F2937"
TEXT_MUTED = "#5F6B7A"
BORDER = "#D7DEE8"
PANEL_BG = "#F5F7FA"
WINDOW_BG = "#EEF2F6"


@dataclass
class CartItem:
    product_id: int
    barcode: str
    name: str
    qty: float
    unit_price: float

    @property
    def subtotal(self) -> float:
        return self.qty * self.unit_price


class SidebarButton(QPushButton):
    def __init__(self, text: str, icon, active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icon)
        self.setIconSize(QSize(18, 18))
        self.setProperty("active", active)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class KeypadButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)


class ActionButton(QPushButton):
    def __init__(self, text: str, style_name: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("role", style_name)
        self.setMinimumHeight(48)


class PosMainWindow(QMainWindow):
    def __init__(self, user_data: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("POS Sales Terminal")
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

        self.build_ui()
        self.populate_cart()
        self.create_shortcuts()

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

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
            self.product_management_page = ProductManagementWindow()
            self.page_indexes["products"] = self.pages.addWidget(self.product_management_page)

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

    def get_today_summary(self) -> dict[str, float | int]:
        today = datetime.now().strftime("%Y-%m-%d")
        with db.get_connection() as connection:
            sales_row = connection.execute(
                """
                SELECT COUNT(*) AS count, COALESCE(SUM(total_amount), 0) AS total
                FROM sales
                WHERE date(created_at) = date(?) AND status = 'completed'
                """,
                (today,),
            ).fetchone()
            items_row = connection.execute(
                """
                SELECT COALESCE(SUM(si.qty), 0) AS items
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE date(s.created_at) = date(?) AND s.status = 'completed'
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

    def create_dashboard_card(self, title: str, value: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setObjectName("dashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("dashboardCardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("dashboardCardValue")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("dashboardCardSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        return card

    def create_dashboard_button(self, text: str, page_key: str, style_name: str = "primary") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("dashboardActionButton")
        button.setProperty("role", style_name)
        button.setMinimumHeight(48)
        button.clicked.connect(lambda _checked=False, key=page_key: self.switch_page(self.page_indexes[key]))
        return button

    def create_cashier_dashboard(self) -> QWidget:
        summary = self.get_today_summary()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Cashier Dashboard")
        title.setObjectName("workspaceTitle")
        subtitle = QLabel(
            f"Welcome {self.user_data.get('full_name', 'Cashier')} | Register #{self.register_id} | Shift #{self.shift_id}"
        )
        subtitle.setObjectName("cashierInfo")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        stats.addWidget(self.create_dashboard_card("Today's Sales", f"{summary['sales_count']}", "Transactions completed"))
        stats.addWidget(self.create_dashboard_card("Revenue", f"${summary['sales_total']:,.2f}", "Collected today"))
        stats.addWidget(self.create_dashboard_card("Items Sold", f"{summary['items_sold']:g}", "Units and weighted items"))
        layout.addLayout(stats)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.create_dashboard_button("Open POS Terminal", "pos_terminal", "primary"))
        actions.addWidget(self.create_dashboard_button("Continue Shift", "pos_terminal", "secondary"))
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def create_manager_dashboard(self) -> QWidget:
        summary = self.get_today_summary()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Manager Dashboard")
        title.setObjectName("workspaceTitle")
        subtitle = QLabel("Monitor sales, registers, shift activity, and daily performance")
        subtitle.setObjectName("cashierInfo")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        stats.addWidget(self.create_dashboard_card("Revenue", f"${summary['sales_total']:,.2f}", "Completed sales today"))
        stats.addWidget(self.create_dashboard_card("Transactions", f"{summary['sales_count']}", "Sales count today"))
        stats.addWidget(self.create_dashboard_card("Avg. Sale", f"${summary['average_sale']:,.2f}", "Average transaction"))
        layout.addLayout(stats)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.create_dashboard_button("View Reports", "reports", "primary"))
        actions.addWidget(self.create_dashboard_button("Manage Registers", "registers", "secondary"))
        if "products" in self.page_indexes:
            actions.addWidget(self.create_dashboard_button("Product Management", "products", "secondary"))
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(10)

        title = QLabel("Retail POS")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel("Sales Terminal")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        style = self.style()
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
                style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon),
            )
        elif role_name == "Manager":
            add_sidebar_button(
                "Manager Dashboard",
                "manager_dashboard",
                style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon),
            )
        elif role_name == "Admin":
            add_sidebar_button(
                "Admin Dashboard",
                "admin_dashboard",
                style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon),
            )

        self.terminal_button = SidebarButton(
            "POS Terminal",
            style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
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
                style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            )

        if role_name == "Manager":
            add_sidebar_button("Reports", "reports", style.standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
            add_sidebar_button("Registers", "registers", style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
            add_sidebar_button("Audit Logs", "audit_logs", style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        elif role_name == "Admin":
            add_sidebar_button("Users", "users", style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            add_sidebar_button("Registers", "registers", style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
            add_sidebar_button("Reports", "reports", style.standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
            add_sidebar_button("Audit Logs", "audit_logs", style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            add_sidebar_button("Settings", "settings", style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))

        self.switch_page(self.pages.currentIndex())

        layout.addStretch(1)

        footer = QLabel("SQLite Desktop Mode")
        footer.setObjectName("sidebarFooter")
        layout.addWidget(footer)

        return sidebar

    def switch_page(self, page_index: int) -> None:
        self.pages.setCurrentIndex(page_index)
        for button, button_page_index in self.sidebar_buttons:
            is_active = button_page_index == page_index
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)

        if page_index == self.page_indexes.get("pos_terminal"):
            self.search_input.setFocus()
        elif page_index == self.page_indexes.get("products") and self.product_management_page is not None:
            self.product_management_page.load_products()

    def create_content_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)

        layout.addWidget(self.create_top_bar())

        workspace = QHBoxLayout()
        workspace.setSpacing(18)
        workspace.addWidget(self.create_cart_panel(), 13)
        workspace.addWidget(self.create_checkout_panel(), 7)

        layout.addLayout(workspace, 1)
        return container

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("POS Terminal")
        heading.setObjectName("workspaceTitle")

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

    def create_cart_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("cardPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scan barcode or search product name...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.handle_product_search)
        layout.addWidget(self.search_input)

        self.cart_table = QTableWidget(0, 6)
        self.cart_table.setHorizontalHeaderLabels(
            ["Barcode", "Product Name", "Qty", "Unit Price", "Subtotal", "Action"]
        )
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setShowGrid(False)
        self.cart_table.setSortingEnabled(False)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(44)
        self.cart_table.horizontalHeader().setStretchLastSection(False)
        self.cart_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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
        self.cart_table.itemSelectionChanged.connect(self.sync_status)
        self.cart_table.itemChanged.connect(self.handle_cart_item_changed)
        layout.addWidget(self.cart_table, 1)

        footer = QLabel("Scan barcode or type a product name, then press Enter")
        footer.setObjectName("statusHint")
        layout.addWidget(footer)
        return panel

    def create_checkout_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("checkoutPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        total_block = QFrame()
        total_block.setObjectName("totalBlock")
        total_layout = QVBoxLayout(total_block)
        total_layout.setContentsMargins(18, 18, 18, 18)
        total_layout.setSpacing(6)

        total_label = QLabel("Total Amount")
        total_label.setObjectName("sectionLabel")

        self.total_value_label = QLabel("$0.00")
        self.total_value_label.setObjectName("totalValue")

        total_layout.addWidget(total_label)
        total_layout.addWidget(self.total_value_label)
        layout.addWidget(total_block)

        tender_title = QLabel("Tendered")
        tender_title.setObjectName("sectionLabel")
        layout.addWidget(tender_title)

        self.tender_input = QLineEdit()
        self.tender_input.setPlaceholderText("Enter amount")
        self.tender_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.tender_input.returnPressed.connect(self.handle_pay_cash)
        layout.addWidget(self.tender_input)

        keypad = QWidget()
        keypad_layout = QGridLayout(keypad)
        keypad_layout.setContentsMargins(0, 0, 0, 0)
        keypad_layout.setHorizontalSpacing(10)
        keypad_layout.setVerticalSpacing(10)

        buttons = [
            ("7", 0, 0),
            ("8", 0, 1),
            ("9", 0, 2),
            ("4", 1, 0),
            ("5", 1, 1),
            ("6", 1, 2),
            ("1", 2, 0),
            ("2", 2, 1),
            ("3", 2, 2),
            ("0", 3, 0),
            (".", 3, 1),
            ("Backspace", 3, 2),
        ]

        for text, row, col in buttons:
            button = KeypadButton(text)
            button.clicked.connect(
                lambda _checked=False, value=text: self.handle_keypad_press(value)
            )
            keypad_layout.addWidget(button, row, col)

        layout.addWidget(keypad)

        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(0, 6, 0, 0)
        action_layout.setSpacing(10)

        pay_cash_button = ActionButton("Pay Cash", "primary")
        split_payment_button = ActionButton("Split Payment", "warning")
        void_button = ActionButton("Void/Cancel (ESC)", "neutral")

        pay_cash_button.clicked.connect(self.handle_pay_cash)
        split_payment_button.clicked.connect(self.handle_split_payment)
        void_button.clicked.connect(self.handle_void_cancel)

        action_layout.addWidget(pay_cash_button)
        action_layout.addWidget(split_payment_button)
        action_layout.addWidget(void_button)

        layout.addLayout(action_layout)
        layout.addStretch(1)
        return panel

    def create_shortcuts(self) -> None:
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.handle_void_cancel)

        focus_search_action = QAction(self)
        focus_search_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_search_action.triggered.connect(self.search_input.setFocus)
        self.addAction(focus_search_action)

    def handle_product_search(self) -> None:
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
            else:
                QMessageBox.warning(self, "Product Not Found", "No product was found.")
            return

        self.add_product_to_cart(product)
        self.search_input.clear()
        self.search_input.setFocus()

    def add_product_to_cart(self, product) -> None:
        product_id = int(product["id"])
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

        for cart_item in self.cart_items:
            if cart_item.product_id == product_id:
                cart_item.qty += quantity
                self.populate_cart()
                self.statusBar().showMessage(f"Quantity increased: {cart_item.name}", 2500)
                return

        self.cart_items.append(
            CartItem(
                product_id=product_id,
                barcode=product["barcode"] or "",
                name=product["name"],
                qty=quantity,
                unit_price=float(product["price"]),
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
                f"${item.unit_price:,.2f}",
                f"${item.subtotal:,.2f}",
            ]
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                table_item.setData(Qt.ItemDataRole.UserRole, item.product_id)
                if column < 2:
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

            delete_button = QPushButton("Delete")
            delete_button.setObjectName("tableDeleteButton")
            delete_button.clicked.connect(
                lambda _checked=False, product_id=item.product_id: self.remove_cart_item(
                    product_id
                )
            )
            self.cart_table.setCellWidget(row, 5, delete_button)

        self.cart_table_updating = False
        self.refresh_total()

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

        for cart_item in self.cart_items:
            if cart_item.product_id == product_id:
                cart_item.qty = new_qty
                break
        self.populate_cart()

    def remove_cart_item(self, product_id: int) -> None:
        self.cart_items = [item for item in self.cart_items if item.product_id != product_id]
        self.populate_cart()

    def refresh_total(self) -> None:
        total = sum(item.subtotal for item in self.cart_items)
        self.total_value_label.setText(f"${total:,.2f}")

    def sync_status(self) -> None:
        selected = self.cart_table.currentRow()
        if selected < 0 or selected >= len(self.cart_items):
            return
        item = self.cart_items[selected]
        self.statusBar().showMessage(f"Selected: {item.name} x{item.qty}", 2500)

    def handle_keypad_press(self, value: str) -> None:
        if value == "Backspace":
            self.tender_input.backspace()
            return
        self.tender_input.insert(value)

    def handle_pay_cash(self) -> None:
        total_amount = self.get_cart_total()
        if total_amount <= 0:
            QMessageBox.warning(self, "Empty Cart", "Please add products before payment.")
            return

        try:
            tendered_amount = self.parse_money(self.tender_input.text())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Tendered Amount",
                "Please enter a valid tendered amount.",
            )
            return

        if tendered_amount < total_amount:
            QMessageBox.warning(
                self,
                "Insufficient Payment",
                "Tendered amount is less than the total amount.",
            )
            return

        change_amount = tendered_amount - total_amount
        sale_items = self.get_sale_items_from_cart_table()

        try:
            sale_id = db.create_sale(
                total_amount,
                "Cash",
                sale_items,
                user_id=int(self.user_data.get("id", 0)),
                register_id=self.register_id,
                shift_id=self.shift_id,
                tendered_amount=tendered_amount,
                change_amount=change_amount,
                payments=[{"method": "Cash", "amount": total_amount}],
            )
            add_cash_movement(
                self.shift_id,
                int(self.user_data.get("id", 0)),
                "sale",
                total_amount,
                f"Cash sale #{sale_id}",
            )
            log_audit(self.user_data["id"], "CREATE_SALE", "sales", sale_id, None, f"total: {total_amount:.2f}")
        except Exception as error:
            QMessageBox.warning(self, "Database Error", f"Could not save sale: {error}")
            return

        QMessageBox.information(
            self,
            "Payment Successful",
            f"Payment successful.\nChange: ${change_amount:,.2f}",
        )
        receipt_text = self.build_receipt_text(
            sale_items=sale_items,
            total_amount=total_amount,
            tendered_amount=tendered_amount,
            change_amount=change_amount,
            payment_method="Cash",
        )
        self.show_receipt_preview(receipt_text)
        self.clear_current_sale()

    def handle_split_payment(self) -> None:
        total_amount = self.get_cart_total()
        if total_amount <= 0:
            QMessageBox.warning(self, "Empty Cart", "Please add products before payment.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Split Payment")
        dialog.setModal(True)
        dialog.setMinimumWidth(390)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        total_label = QLabel(f"Total Amount: ${total_amount:,.2f}")
        total_label.setObjectName("dialogTotalLabel")
        layout.addWidget(total_label)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)

        cash_input = QLineEdit()
        cash_input.setPlaceholderText("0.00")
        cash_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        card_input = QLineEdit()
        card_input.setPlaceholderText("0.00")
        card_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        form_layout.addRow("Cash", cash_input)
        form_layout.addRow("Card/Transfer", card_input)
        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("neutralDialogButton")
        cancel_button.clicked.connect(dialog.reject)

        confirm_button = QPushButton("Confirm")
        confirm_button.setObjectName("primaryDialogButton")

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        layout.addLayout(button_layout)

        def confirm_split_payment() -> None:
            try:
                cash_amount = self.parse_money(cash_input.text() or "0")
                card_amount = self.parse_money(card_input.text() or "0")
            except ValueError:
                QMessageBox.warning(dialog, "Invalid Amount", "Please enter valid payment amounts.")
                return

            tendered_amount = cash_amount + card_amount
            if tendered_amount < total_amount:
                QMessageBox.warning(
                    dialog,
                    "Insufficient Payment",
                    "Cash plus Card/Transfer amount is less than the total amount.",
                )
                return

            change_amount = tendered_amount - total_amount
            sale_items = self.get_sale_items_from_cart_table()

            try:
                sale_id = db.create_sale(
                    total_amount,
                    "Split",
                    sale_items,
                    user_id=int(self.user_data.get("id", 0)),
                    register_id=self.register_id,
                    shift_id=self.shift_id,
                    tendered_amount=tendered_amount,
                    change_amount=change_amount,
                    payments=[
                        {"method": "Cash", "amount": cash_amount},
                        {"method": "Card/Transfer", "amount": card_amount},
                    ],
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
            except Exception as error:
                QMessageBox.warning(dialog, "Database Error", f"Could not save sale: {error}")
                return

            QMessageBox.information(
                self,
                "Payment Successful",
                f"Payment successful.\nChange: ${change_amount:,.2f}",
            )
            receipt_text = self.build_receipt_text(
                sale_items=sale_items,
                total_amount=total_amount,
                tendered_amount=tendered_amount,
                change_amount=change_amount,
                payment_method="Split",
            )
            dialog.accept()
            self.show_receipt_preview(receipt_text)
            self.clear_current_sale()

        confirm_button.clicked.connect(confirm_split_payment)
        dialog.exec()

    def handle_void_cancel(self) -> None:
        if not self.cart_items and not self.tender_input.text().strip():
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
        clean_value = value.strip().replace("$", "").replace(",", "")
        if not clean_value:
            raise ValueError("Empty amount")
        amount = float(clean_value)
        if amount < 0:
            raise ValueError("Negative amount")
        return amount

    def get_cart_total(self) -> float:
        return sum(item.subtotal for item in self.cart_items)

    def get_sale_items_from_cart_table(self) -> list[dict[str, object]]:
        sale_items = []
        for row in range(self.cart_table.rowCount()):
            barcode_item = self.cart_table.item(row, 0)
            name_item = self.cart_table.item(row, 1)
            qty_item = self.cart_table.item(row, 2)
            price_item = self.cart_table.item(row, 3)
            subtotal_item = self.cart_table.item(row, 4)
            if not all([barcode_item, name_item, qty_item, price_item, subtotal_item]):
                continue

            sale_items.append(
                {
                    "barcode": barcode_item.text(),
                    "product_id": int(barcode_item.data(Qt.ItemDataRole.UserRole) or 0),
                    "name": name_item.text(),
                    "qty": float(qty_item.text()),
                    "price": self.parse_money(price_item.text()),
                    "subtotal": self.parse_money(subtotal_item.text()),
                }
            )
        return sale_items

    def build_receipt_text(
        self,
        sale_items: list[dict[str, object]],
        total_amount: float,
        tendered_amount: float,
        change_amount: float,
        payment_method: str,
    ) -> str:
        line_width = 42
        lines = [
            "MY POS SHOP".center(line_width),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S").center(line_width),
            f"Payment: {payment_method}".center(line_width),
            "-" * line_width,
            f"{'Item':<18}{'Qty':>4}{'Price':>9}{'Amount':>11}",
            "-" * line_width,
        ]

        for item in sale_items:
            name = str(item["name"])[:18]
            qty = float(item["qty"])
            price = float(item["price"])
            subtotal = float(item["subtotal"])
            lines.append(f"{name:<18}{qty:>4g}{price:>9.2f}{subtotal:>11.2f}")

        lines.extend(
            [
                "-" * line_width,
                f"{'Total':<22}${total_amount:>18,.2f}",
                f"{'Tendered':<22}${tendered_amount:>18,.2f}",
                f"{'Change':<22}${change_amount:>18,.2f}",
                "-" * line_width,
                "Thank you for shopping!".center(line_width),
            ]
        )
        return "\n".join(lines)

    def show_receipt_preview(self, receipt_text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Receipt Preview")
        dialog.setModal(True)
        dialog.resize(460, 620)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        receipt_view = QTextEdit()
        receipt_view.setReadOnly(True)
        receipt_view.setPlainText(receipt_text)
        receipt_view.setFont(QFont("Consolas", 10))
        layout.addWidget(receipt_view, 1)

        close_button = QPushButton("Close")
        close_button.setObjectName("primaryDialogButton")
        close_button.clicked.connect(dialog.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        dialog.exec()

    def clear_current_sale(self) -> None:
        self.cart_items.clear()
        self.populate_cart()
        self.tender_input.clear()
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

    #cardPanel, #checkoutPanel {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
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
        border-radius: 10px;
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

    #statusHint {{
        color: {TEXT_MUTED};
        font-size: 12px;
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

    #tableDeleteButton {{
        background: #DC2626;
        border: none;
        border-radius: 6px;
        color: #FFFFFF;
        font-weight: 700;
        padding: 6px 10px;
    }}

    #tableDeleteButton:hover {{
        background: #B91C1C;
    }}

    #dialogTotalLabel {{
        color: {TEXT_DARK};
        font-size: 16px;
        font-weight: 700;
    }}

    #primaryDialogButton {{
        background: {ACCENT_BLUE};
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-weight: 700;
        padding: 9px 16px;
    }}

    #neutralDialogButton {{
        background: #E5E7EB;
        border: none;
        border-radius: 8px;
        color: {TEXT_DARK};
        font-weight: 700;
        padding: 9px 16px;
    }}
    """


def configure_app_font(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    app.setFont(QFont("Segoe UI", 10))
