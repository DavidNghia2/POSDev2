from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLayout,
    QLayoutItem,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import db
from login import get_setting
from ui.currency import format_money, get_currency_symbol_from_settings
from ui.icon_manager import IconManager
from ui.theme import MODERN_WIDGET_STYLESHEET


def get_sales_summary(start_date: str, end_date: str) -> dict:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        # Get total sales count and amount
        cursor = connection.execute(
            """
            SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE store_id = ?
              AND datetime(created_at, 'localtime') >= datetime(?)
              AND datetime(created_at, 'localtime') <= datetime(?)
              AND status = 'completed'
            """,
            (store_id, start_date, end_date),
        )
        row = cursor.fetchone()
        
        # Get items sold
        cursor = connection.execute(
            """
            SELECT COALESCE(SUM(qty), 0) as items_sold
            FROM sale_items
            WHERE sale_id IN (
                SELECT id
                FROM sales
                WHERE store_id = ?
                  AND datetime(created_at, 'localtime') >= datetime(?)
                  AND datetime(created_at, 'localtime') <= datetime(?)
                AND status = 'completed'
            ) AND store_id = ?
            """,
            (store_id, start_date, end_date, store_id),
        )
        items_row = cursor.fetchone()
        
        # Get payment method breakdown from payment rows so split payments are counted correctly.
        cursor = connection.execute(
            """
            WITH payment_rows AS (
                SELECT sp.sale_id, sp.method as payment_method, sp.amount
                FROM sale_payments sp
                JOIN sales s ON s.id = sp.sale_id
                WHERE sp.store_id = ? AND s.store_id = ?
                  AND datetime(s.created_at, 'localtime') >= datetime(?)
                  AND datetime(s.created_at, 'localtime') <= datetime(?)
                  AND s.status = 'completed'

                UNION ALL

                SELECT s.id as sale_id, s.payment_method, s.total_amount as amount
                FROM sales s
                WHERE s.store_id = ?
                  AND datetime(s.created_at, 'localtime') >= datetime(?)
                  AND datetime(s.created_at, 'localtime') <= datetime(?)
                  AND s.status = 'completed'
                  AND NOT EXISTS (
                      SELECT 1 FROM sale_payments sp WHERE sp.sale_id = s.id AND sp.store_id = ?
                  )
            )
            SELECT payment_method,
                   COUNT(DISTINCT sale_id) as count,
                   COALESCE(SUM(amount), 0) as total
            FROM payment_rows
            GROUP BY payment_method
            ORDER BY total DESC
            """,
            (store_id, store_id, start_date, end_date, store_id, start_date, end_date, store_id),
        )
        payment_stats = cursor.fetchall()
        
        # Get today's sales for comparison
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = connection.execute(
            """
            SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE store_id = ?
              AND date(created_at, 'localtime') = date(?)
              AND status = 'completed'
            """,
            (store_id, today),
        )
        today_row = cursor.fetchone()
        
        return {
            "count": row["count"] if row else 0,
            "total": row["total"] if row else 0.0,
            "items_sold": items_row["items_sold"] if items_row else 0,
            "payment_breakdown": [
                {"method": p["payment_method"], "count": p["count"], "total": p["total"]}
                for p in payment_stats
            ],
            "today_count": today_row["count"] if today_row else 0,
            "today_total": today_row["total"] if today_row else 0.0,
        }


def get_top_products(start_date: str, end_date: str, limit: int = 5) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            WITH resolved_items AS (
                SELECT
                    COALESCE(
                        'product:' || product_by_id.id,
                        'product:' || product_by_barcode.id,
                        'barcode:' || NULLIF(si.barcode, ''),
                        'name:' || NULLIF(si.name, ''),
                        'item:' || si.id
                    ) as product_key,
                    COALESCE(product_by_id.barcode, product_by_barcode.barcode, si.barcode) as barcode,
                    COALESCE(
                        product_by_id.name,
                        product_by_barcode.name,
                        NULLIF(si.name, ''),
                        NULLIF(si.barcode, ''),
                        'Unknown Product'
                    ) as name,
                    si.qty,
                    si.subtotal
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                LEFT JOIN products product_by_id ON product_by_id.id = si.product_id AND product_by_id.store_id = ?
                LEFT JOIN products product_by_barcode
                    ON si.product_id IS NULL
                   AND product_by_barcode.barcode = si.barcode
                   AND product_by_barcode.store_id = ?
                WHERE si.store_id = ? AND s.store_id = ?
                  AND datetime(s.created_at, 'localtime') >= datetime(?)
                  AND datetime(s.created_at, 'localtime') <= datetime(?)
                  AND s.status = 'completed'
            )
            SELECT barcode, name, SUM(qty) as total_qty, SUM(subtotal) as total_sales
            FROM resolved_items
            GROUP BY product_key
            ORDER BY total_sales DESC
            LIMIT ?
            """,
            (store_id, store_id, store_id, store_id, start_date, end_date, limit),
        )
        return cursor.fetchall()


def get_low_stock_products(threshold: int = 10) -> list:
    # This would require stock tracking - placeholder for now
    return []


def current_currency_symbol() -> str:
    return get_currency_symbol_from_settings(get_setting)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        clear_layout_item(item)


def clear_layout_item(item: QLayoutItem) -> None:
    child_layout = item.layout()
    if child_layout is not None:
        clear_layout(child_layout)
        child_layout.deleteLater()
        return

    widget = item.widget()
    if widget is not None:
        widget.deleteLater()


class StatCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        icon_key: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        header.setSpacing(10)
        
        if icon_key:
            icon_label = QLabel()
            icon_label.setObjectName("statIcon")
            icon_label.setPixmap(IconManager.pixmap(icon_key, 18))
            icon_label.setFixedSize(18, 18)
            header.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setObjectName("statTitle")
        
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)
        
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        layout.addWidget(value_label)
        
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("statSubtitle")
            layout.addWidget(subtitle_label)
        
        layout.addStretch()

    def set_value(self, value: str) -> None:
        for child in self.findChildren(QLabel, "statValue"):
            child.setText(value)


class AdminDashboardWindow(QWidget):
    def __init__(self, user_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.user_data = user_data
        self.create_ui()
        self.load_dashboard_data()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = IconManager.label("Admin Dashboard", "dashboard", "titleLabel", icon_size=20)
        
        subtitle_label = QLabel("Overview and statistics")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        # Date filters
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        
        date_layout.addWidget(QLabel("From:"))
        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDateTime(
            datetime.now().replace(hour=0, minute=0, second=0)
        )
        self.start_date_input.dateChanged.connect(self.load_dashboard_data)
        
        date_layout.addWidget(self.start_date_input)
        date_layout.addWidget(QLabel("To:"))
        self.end_date_input = QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDateTime(datetime.now())
        self.end_date_input.dateChanged.connect(self.load_dashboard_data)
        
        date_layout.addWidget(self.end_date_input)
        date_layout.addStretch()
        
        header_layout.addLayout(date_layout)
        layout.addLayout(header_layout)
        
        # Stats cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.sales_count_card = StatCard("Total Sales", "0", "sales", "Number of transactions")
        self.revenue_card = StatCard(
            "Revenue",
            format_money(0, current_currency_symbol()),
            "cash",
            "Total sales amount",
        )
        self.items_sold_card = StatCard("Items Sold", "0", "items", "Products sold")
        self.avg_transaction_card = StatCard(
            "Avg. Transaction",
            format_money(0, current_currency_symbol()),
            "average",
            "Per sale",
        )
        
        stats_layout.addWidget(self.sales_count_card)
        stats_layout.addWidget(self.revenue_card)
        stats_layout.addWidget(self.items_sold_card)
        stats_layout.addWidget(self.avg_transaction_card)
        
        layout.addLayout(stats_layout)
        
        # Content split
        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        
        # Left panel - payment breakdown
        left_panel = QFrame()
        left_panel.setObjectName("panel")
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(22, 22, 22, 22)
        left_layout.setSpacing(14)
        
        section_label = IconManager.label("Payment Methods", "payment", "sectionLabel")
        left_layout.addWidget(section_label)
        
        self.payment_table = QVBoxLayout()
        self.payment_table.setSpacing(8)
        left_layout.addLayout(self.payment_table)
        
        left_layout.addStretch()
        
        content_layout.addWidget(left_panel, 1)
        
        # Right panel - top products
        right_panel = QFrame()
        right_panel.setObjectName("panel")
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(22, 22, 22, 22)
        right_layout.setSpacing(14)
        
        section_label = IconManager.label("Top Selling Products", "products", "sectionLabel")
        right_layout.addWidget(section_label)
        
        self.top_products_layout = QVBoxLayout()
        self.top_products_layout.setSpacing(8)
        right_layout.addLayout(self.top_products_layout)
        
        right_layout.addStretch()
        
        content_layout.addWidget(right_panel, 1)
        
        layout.addLayout(content_layout, 1)

    def load_dashboard_data(self) -> None:
        start_date = self.start_date_input.date().toString("yyyy-MM-dd")
        end_date = self.end_date_input.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        summary = get_sales_summary(start_date, end_date)
        currency_symbol = current_currency_symbol()
        
        # Update stat cards
        self.sales_count_card.set_value(str(summary["count"]))
        self.revenue_card.set_value(format_money(float(summary["total"]), currency_symbol))
        self.items_sold_card.set_value(str(summary["items_sold"]))
        
        avg = summary["total"] / summary["count"] if summary["count"] > 0 else 0
        self.avg_transaction_card.set_value(format_money(float(avg), currency_symbol))
        
        # Update payment breakdown
        self.update_payment_breakdown(summary["payment_breakdown"])
        
        # Update top products
        self.update_top_products(start_date, end_date)

    def update_payment_breakdown(self, payment_data: list) -> None:
        clear_layout(self.payment_table)
        currency_symbol = current_currency_symbol()
        
        for payment in payment_data:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(10)
            
            method_label = QLabel(payment["method"] or "Unknown")
            method_label.setObjectName("paymentMethod")
            
            count_label = QLabel(f"{payment['count']} sales")
            count_label.setObjectName("paymentCount")
            
            amount_label = QLabel(format_money(float(payment["total"]), currency_symbol))
            amount_label.setObjectName("paymentAmount")
            amount_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            row_layout.addWidget(method_label)
            row_layout.addStretch()
            row_layout.addWidget(count_label)
            row_layout.addWidget(amount_label)
            
            self.payment_table.addLayout(row_layout)
        
        if not payment_data:
            no_data_label = QLabel("No payment data available")
            no_data_label.setObjectName("noDataLabel")
            self.payment_table.addWidget(no_data_label)

    def update_top_products(self, start_date: str, end_date: str) -> None:
        clear_layout(self.top_products_layout)
        currency_symbol = current_currency_symbol()
        
        top_products = get_top_products(start_date, end_date, 5)
        
        for product in top_products:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(10)
            
            name_label = QLabel(str(product["name"])[:30])
            name_label.setObjectName("productName")
            name_label.setWordWrap(False)
            
            qty_label = QLabel(f"x{product['total_qty']}")
            qty_label.setObjectName("productQty")
            
            sales_label = QLabel(format_money(float(product["total_sales"]), currency_symbol))
            sales_label.setObjectName("productSales")
            sales_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            row_layout.addWidget(name_label)
            row_layout.addStretch()
            row_layout.addWidget(qty_label)
            row_layout.addWidget(sales_label)
            
            self.top_products_layout.addLayout(row_layout)
        
        if not top_products:
            no_data_label = QLabel("No sales data available")
            no_data_label.setObjectName("noDataLabel")
            self.top_products_layout.addWidget(no_data_label)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #EEF1F4;
                color: #1F2933;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            #titleLabel {
                color: #17212B;
                font-size: 26px;
                font-weight: 700;
            }

            #subtitleLabel {
                color: #64707D;
                font-size: 13px;
            }

            #sectionLabel {
                color: #25313D;
                font-size: 15px;
                font-weight: 700;
            }

            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
            }

            #statCard {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
                min-width: 180px;
            }

            #statIcon {
                font-size: 20px;
            }

            #statTitle {
                color: #64707D;
                font-size: 12px;
                font-weight: 600;
            }

            #statValue {
                color: #17212B;
                font-size: 24px;
                font-weight: 800;
            }

            #statSubtitle {
                color: #94A3B8;
                font-size: 11px;
            }

            #paymentMethod {
                font-weight: 600;
                min-width: 100px;
            }

            #paymentCount {
                color: #64707D;
            }

            #paymentAmount {
                font-weight: 700;
                color: #0F766E;
            }

            #productName {
                font-weight: 500;
            }

            #productQty {
                color: #64707D;
            }

            #productSales {
                font-weight: 700;
                color: #0F766E;
            }

            #noDataLabel {
                color: #94A3B8;
                font-style: italic;
            }

            QLabel {
                background: transparent;
            }

            QDateEdit {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 8px 12px;
            }

            QDateEdit:focus {
                border: 1px solid #2563EB;
            }

            QDateEdit::drop-down {
                border: none;
                width: 24px;
            }
            """ + MODERN_WIDGET_STYLESHEET
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_admin_dashboard(user_data: dict) -> AdminDashboardWindow:
    window = AdminDashboardWindow(user_data)
    return window
