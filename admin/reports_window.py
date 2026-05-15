from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import db
from ui.icon_manager import IconManager


def get_sales_report(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT s.id, s.total_amount, s.payment_method, s.created_at,
                   u.username as cashier_name
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.created_at >= ? AND s.created_at <= ?
              AND s.status = 'completed'
            ORDER BY s.id DESC
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_cashier(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT u.username as cashier_name, 
                   COUNT(s.id) as transaction_count,
                   COALESCE(SUM(s.total_amount), 0) as total_sales
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.created_at >= ? AND s.created_at <= ?
              AND s.status = 'completed'
            GROUP BY s.user_id
            ORDER BY total_sales DESC
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_payment(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT payment_method,
                   COUNT(*) as transaction_count,
                   COALESCE(SUM(total_amount), 0) as total_sales
            FROM sales
            WHERE created_at >= ? AND created_at <= ?
              AND status = 'completed'
            GROUP BY payment_method
            ORDER BY total_sales DESC
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_product(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT si.barcode, si.name,
                   SUM(si.qty) as quantity_sold,
                   SUM(si.subtotal) as total_sales
            FROM sale_items si
            WHERE si.sale_id IN (
                SELECT id FROM sales WHERE created_at >= ? AND created_at <= ?
                AND status = 'completed'
            )
            GROUP BY si.barcode, si.name
            ORDER BY total_sales DESC
            LIMIT 50
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


def get_voided_sales_report(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT s.id, s.total_amount, s.payment_method, s.created_at,
                   u.username as cashier_name
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.created_at >= ? AND s.created_at <= ?
              AND s.status = 'voided'
            ORDER BY s.id DESC
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


def get_shift_summary(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT cs.id, r.name as register_name, u.username as cashier_name,
                   cs.opened_at, cs.closed_at, cs.opening_balance,
                   cs.expected_balance, cs.closing_balance, cs.status
            FROM cash_shifts cs
            LEFT JOIN registers r ON cs.register_id = r.id
            LEFT JOIN users u ON cs.user_id = u.id
            WHERE cs.opened_at >= ? AND cs.opened_at <= ?
            ORDER BY cs.id DESC
            """,
            (start_date, end_date),
        )
        return cursor.fetchall()


class ReportsWindow(QWidget):
    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.create_ui()
        self.load_report()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = IconManager.label("Reports", "reports", "titleLabel", icon_size=20)
        
        subtitle_label = QLabel("Sales and transaction reports")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Filters
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(12)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        
        # Report type
        filters_layout.addWidget(QLabel("Report:"))
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Daily Sales",
            "Voided Sales",
            "Sales by Cashier",
            "Shift Summary",
            "Sales by Payment",
            "Sales by Product",
        ])
        self.report_type_combo.currentIndexChanged.connect(self.load_report)
        filters_layout.addWidget(self.report_type_combo)
        
        # Date from
        filters_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDateTime(
            datetime.now().replace(hour=0, minute=0, second=0)
        )
        self.date_from.dateChanged.connect(self.load_report)
        filters_layout.addWidget(self.date_from)
        
        # Date to
        filters_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDateTime(datetime.now())
        self.date_to.dateChanged.connect(self.load_report)
        filters_layout.addWidget(self.date_to)
        
        # Quick filters
        filters_layout.addStretch()
        
        self.today_button = QPushButton("Today")
        IconManager.apply_button(self.today_button, "today")
        self.today_button.setObjectName("filterButton")
        self.today_button.clicked.connect(lambda: self.set_date_range("today"))
        filters_layout.addWidget(self.today_button)
        
        self.week_button = QPushButton("This Week")
        IconManager.apply_button(self.week_button, "week")
        self.week_button.setObjectName("filterButton")
        self.week_button.clicked.connect(lambda: self.set_date_range("week"))
        filters_layout.addWidget(self.week_button)
        
        self.month_button = QPushButton("This Month")
        IconManager.apply_button(self.month_button, "month")
        self.month_button.setObjectName("filterButton")
        self.month_button.clicked.connect(lambda: self.set_date_range("month"))
        filters_layout.addWidget(self.month_button)
        
        layout.addLayout(filters_layout)
        
        # Report table
        report_panel = QFrame()
        report_panel.setObjectName("panel")
        
        report_layout = QVBoxLayout(report_panel)
        report_layout.setContentsMargins(18, 18, 18, 18)
        report_layout.setSpacing(12)
        
        self.report_table = QTableWidget()
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setShowGrid(False)
        self.report_table.verticalHeader().setVisible(False)
        
        header = self.report_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        report_layout.addWidget(self.report_table, 1)
        
        layout.addWidget(report_panel, 1)

    def set_date_range(self, period: str) -> None:
        today = datetime.now()
        
        if period == "today":
            start = today.replace(hour=0, minute=0, second=0)
            end = today
        elif period == "week":
            start = today - timedelta(days=today.weekday())
            start = start.replace(hour=0, minute=0, second=0)
            end = today
        elif period == "month":
            start = today.replace(day=1, hour=0, minute=0, second=0)
            end = today
        else:
            return
        
        self.date_from.setDateTime(start)
        self.date_to.setDateTime(end)

    def load_report(self) -> None:
        report_type = self.report_type_combo.currentText()
        start_date = self.date_from.date().toString("yyyy-MM-dd")
        end_date = self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        if report_type == "Daily Sales":
            self.load_daily_sales(start_date, end_date)
        elif report_type == "Voided Sales":
            self.load_voided_sales(start_date, end_date)
        elif report_type == "Sales by Cashier":
            self.load_sales_by_cashier(start_date, end_date)
        elif report_type == "Shift Summary":
            self.load_shift_summary(start_date, end_date)
        elif report_type == "Sales by Payment":
            self.load_sales_by_payment(start_date, end_date)
        elif report_type == "Sales by Product":
            self.load_sales_by_product(start_date, end_date)

    def load_daily_sales(self, start_date: str, end_date: str) -> None:
        data = get_sales_report(start_date, end_date)
        
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels([
            "Sale ID", "Date/Time", "Cashier", "Payment", "Total"
        ])
        
        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                str(row["id"]),
                row["created_at"][:19] if row["created_at"] else "",
                row["cashier_name"] or "N/A",
                row["payment_method"],
                f"${row['total_amount']:,.2f}",
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_voided_sales(self, start_date: str, end_date: str) -> None:
        data = get_voided_sales_report(start_date, end_date)
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels([
            "Sale ID", "Date/Time", "Cashier", "Payment", "Total"
        ])

        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                str(row["id"]),
                row["created_at"][:19] if row["created_at"] else "",
                row["cashier_name"] or "N/A",
                row["payment_method"],
                f"${row['total_amount']:,.2f}",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_cashier(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_cashier(start_date, end_date)
        
        self.report_table.setColumnCount(4)
        self.report_table.setHorizontalHeaderLabels([
            "Cashier", "Transactions", "Total Sales", "Average"
        ])
        
        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            avg = row["total_sales"] / row["transaction_count"] if row["transaction_count"] > 0 else 0
            values = [
                row["cashier_name"] or "N/A",
                str(row["transaction_count"]),
                f"${row['total_sales']:,.2f}",
                f"${avg:,.2f}",
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_shift_summary(self, start_date: str, end_date: str) -> None:
        data = get_shift_summary(start_date, end_date)
        self.report_table.setColumnCount(8)
        self.report_table.setHorizontalHeaderLabels([
            "Shift", "Register", "Cashier", "Opened", "Closed",
            "Opening", "Expected", "Status"
        ])

        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                str(row["id"]),
                row["register_name"] or "N/A",
                row["cashier_name"] or "N/A",
                row["opened_at"][:19] if row["opened_at"] else "",
                row["closed_at"][:19] if row["closed_at"] else "",
                f"${row['opening_balance']:,.2f}",
                f"${row['expected_balance']:,.2f}" if row["expected_balance"] is not None else "$0.00",
                row["status"],
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_payment(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_payment(start_date, end_date)
        
        self.report_table.setColumnCount(3)
        self.report_table.setHorizontalHeaderLabels([
            "Payment Method", "Transactions", "Total"
        ])
        
        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                row["payment_method"],
                str(row["transaction_count"]),
                f"${row['total_sales']:,.2f}",
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_product(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_product(start_date, end_date)
        
        self.report_table.setColumnCount(4)
        self.report_table.setHorizontalHeaderLabels([
            "Barcode", "Product Name", "Qty Sold", "Total Sales"
        ])
        
        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                row["barcode"] or "",
                row["name"] or "",
                str(row["quantity_sold"]),
                f"${row['total_sales']:,.2f}",
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

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

            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
            }

            QComboBox, QDateEdit {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 8px 12px;
                min-width: 120px;
            }

            QComboBox:focus, QDateEdit:focus {
                border: 1px solid #2563EB;
            }

            #filterButton {
                background: #F3F4F6;
                border: 1px solid #D8E0E8;
                border-radius: 6px;
                color: #374151;
                font-weight: 600;
                padding: 8px 12px;
            }

            #filterButton:hover {
                background: #E5E7EB;
            }

            QTableWidget {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 8px;
                alternate-background-color: #F7F9FB;
                gridline-color: transparent;
            }

            QHeaderView::section {
                background: #F0F4F8;
                border: none;
                border-bottom: 1px solid #D8E0E8;
                color: #25313D;
                font-weight: 700;
                padding: 10px;
            }

            QTableWidget::item {
                border-bottom: 1px solid #EDF1F5;
                padding: 8px;
            }
            """
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_reports(current_user: dict) -> ReportsWindow:
    window = ReportsWindow(current_user)
    return window
