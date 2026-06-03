from datetime import datetime, timedelta
from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import db
from login import get_setting
from ui.currency import format_money, get_currency_symbol_from_settings
from ui.icon_manager import IconManager
from ui.theme import MODERN_WIDGET_STYLESHEET


def get_sales_report(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT s.id, s.total_amount, s.payment_method, s.created_at,
                   COALESCE(u.full_name, u.username) as cashier_name
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id AND u.store_id = s.store_id
            WHERE s.store_id = ? AND datetime(s.created_at) >= datetime(?) AND datetime(s.created_at) <= datetime(?)
              AND s.status = 'completed'
            ORDER BY s.id DESC
            """,
            (store_id, start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_cashier(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT COALESCE(u.full_name, u.username, 'N/A') as cashier_name,
                   COUNT(s.id) as transaction_count,
                   COALESCE(SUM(s.total_amount), 0) as total_sales
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id AND u.store_id = s.store_id
            WHERE s.store_id = ? AND datetime(s.created_at) >= datetime(?) AND datetime(s.created_at) <= datetime(?)
              AND s.status = 'completed'
            GROUP BY s.user_id, cashier_name
            ORDER BY total_sales DESC
            """,
            (store_id, start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_payment(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT payment_method,
                   COUNT(*) as transaction_count,
                   COALESCE(SUM(total_amount), 0) as total_sales
            FROM sales
            WHERE store_id = ? AND datetime(created_at) >= datetime(?) AND datetime(created_at) <= datetime(?)
              AND status = 'completed'
            GROUP BY payment_method
            ORDER BY total_sales DESC
            """,
            (store_id, start_date, end_date),
        )
        return cursor.fetchall()


def get_sales_by_product(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT si.barcode, si.name,
                   SUM(si.qty) as quantity_sold,
                   SUM(si.subtotal) as total_sales
            FROM sale_items si
            WHERE si.store_id = ? AND si.sale_id IN (
                SELECT id FROM sales
                WHERE store_id = ? AND datetime(created_at) >= datetime(?) AND datetime(created_at) <= datetime(?)
                AND status = 'completed'
            )
            GROUP BY si.barcode, si.name
            ORDER BY total_sales DESC
            LIMIT 50
            """,
            (store_id, store_id, start_date, end_date),
        )
        return cursor.fetchall()


def get_voided_sales_report(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT s.id, s.total_amount, s.payment_method, s.created_at,
                   COALESCE(u.full_name, u.username) as cashier_name
            FROM sales s
            LEFT JOIN users u ON s.user_id = u.id AND u.store_id = s.store_id
            WHERE s.store_id = ? AND datetime(s.created_at) >= datetime(?) AND datetime(s.created_at) <= datetime(?)
              AND s.status = 'voided'
            ORDER BY s.id DESC
            """,
            (store_id, start_date, end_date),
        )
        return cursor.fetchall()


def get_shift_summary(start_date: str, end_date: str) -> list:
    with db.get_connection() as connection:
        store_id = db.current_store_id_from_connection(connection)
        cursor = connection.execute(
            """
            SELECT cs.id, r.name as register_name, COALESCE(u.full_name, u.username) as cashier_name,
                   cs.opened_at, cs.closed_at, cs.opening_balance,
                   cs.expected_balance, cs.closing_balance, cs.status
            FROM cash_shifts cs
            LEFT JOIN registers r ON cs.register_id = r.id AND r.store_id = cs.store_id
            LEFT JOIN users u ON cs.user_id = u.id AND u.store_id = cs.store_id
            WHERE cs.store_id = ? AND datetime(cs.opened_at) >= datetime(?) AND datetime(cs.opened_at) <= datetime(?)
            ORDER BY cs.id DESC
            """,
            (store_id, start_date, end_date),
        )
        return cursor.fetchall()


def current_currency_symbol() -> str:
    return get_currency_symbol_from_settings(get_setting)


class ReportsWindow(QWidget):
    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self._setting_preset_range = False
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
        self.date_from.dateChanged.connect(self.on_manual_date_changed)
        filters_layout.addWidget(self.date_from)
        
        # Date to
        filters_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDateTime(datetime.now())
        self.date_to.dateChanged.connect(self.on_manual_date_changed)
        filters_layout.addWidget(self.date_to)
        
        # Quick filters
        filters_layout.addStretch()

        self.date_range_button = QPushButton("Today")
        IconManager.apply_button(self.date_range_button, "today")
        self.date_range_button.setObjectName("filterButton")

        self.date_range_menu = QMenu(self)
        today_action = self.date_range_menu.addAction("Today")
        week_action = self.date_range_menu.addAction("This Week")
        month_action = self.date_range_menu.addAction("This Month")
        today_action.triggered.connect(lambda: self.set_date_range("today"))
        week_action.triggered.connect(lambda: self.set_date_range("week"))
        month_action.triggered.connect(lambda: self.set_date_range("month"))
        self.date_range_button.setMenu(self.date_range_menu)
        filters_layout.addWidget(self.date_range_button)

        self.print_button = QPushButton("Print Report")
        IconManager.apply_button(self.print_button, "reports")
        self.print_button.setObjectName("primaryButton")
        self.print_button.clicked.connect(self.print_report)
        filters_layout.addWidget(self.print_button)
        
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
        
        labels = {
            "today": "Today",
            "week": "This Week",
            "month": "This Month",
        }
        self._setting_preset_range = True
        self.date_range_button.setText(labels[period])
        self.date_from.setDateTime(start)
        self.date_to.setDateTime(end)
        self._setting_preset_range = False
        self.load_report()

    def on_manual_date_changed(self) -> None:
        if self._setting_preset_range:
            return
        self.date_range_button.setText("Custom Range")
        self.load_report()

    def load_report(self) -> None:
        report_type = self.report_type_combo.currentText()
        start_date = self.date_from.date().toString("yyyy-MM-dd") + " 00:00:00"
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

    def print_report(self) -> None:
        # Refresh first so the printed copy always mirrors the latest selected report.
        self.load_report()

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(f"{self.report_type_combo.currentText()} Report")
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Print Preview - Report")
        preview.resize(1100, 800)
        preview.paintRequested.connect(self.render_report_to_printer)
        preview.exec()

    def render_report_to_printer(self, printer: QPrinter) -> None:
        document = QTextDocument(self)
        document.setHtml(self.build_report_html())
        document.print(printer)

    def build_report_html(self) -> str:
        report_type = self.report_type_combo.currentText()
        start_date = self.date_from.date().toString("yyyy-MM-dd")
        end_date = self.date_to.date().toString("yyyy-MM-dd")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        headers = []
        for column in range(self.report_table.columnCount()):
            header_item = self.report_table.horizontalHeaderItem(column)
            headers.append(header_item.text() if header_item else "")

        rows = []
        for row in range(self.report_table.rowCount()):
            values = []
            for column in range(self.report_table.columnCount()):
                item = self.report_table.item(row, column)
                values.append(item.text() if item else "")
            rows.append(values)

        header_html = "".join(f"<th>{escape(value)}</th>" for value in headers)
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{escape(value)}</td>" for value in values) + "</tr>"
            for values in rows
        )
        empty_state = (
            f"<tr><td colspan='{max(len(headers), 1)}'>No data for the selected period.</td></tr>"
            if not rows
            else ""
        )

        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: "Segoe UI", Arial, sans-serif;
                        color: #1F2933;
                    }}
                    h1 {{
                        margin-bottom: 4px;
                    }}
                    .meta {{
                        color: #4B5563;
                        margin-bottom: 18px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    th, td {{
                        border: 1px solid #D1D5DB;
                        padding: 8px;
                        text-align: center;
                    }}
                    th {{
                        background: #E5E7EB;
                    }}
                </style>
            </head>
            <body>
                <h1>{escape(report_type)}</h1>
                <div class="meta">
                    Period: {escape(start_date)} to {escape(end_date)}<br>
                    Generated: {escape(generated_at)}
                </div>
                <table>
                    <thead><tr>{header_html}</tr></thead>
                    <tbody>{rows_html or empty_state}</tbody>
                </table>
            </body>
        </html>
        """

    def load_daily_sales(self, start_date: str, end_date: str) -> None:
        data = get_sales_report(start_date, end_date)
        currency_symbol = current_currency_symbol()
        
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
                format_money(float(row["total_amount"]), currency_symbol),
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_voided_sales(self, start_date: str, end_date: str) -> None:
        data = get_voided_sales_report(start_date, end_date)
        currency_symbol = current_currency_symbol()
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
                format_money(float(row["total_amount"]), currency_symbol),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_cashier(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_cashier(start_date, end_date)
        currency_symbol = current_currency_symbol()
        
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
                format_money(float(row["total_sales"]), currency_symbol),
                format_money(float(avg), currency_symbol),
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_shift_summary(self, start_date: str, end_date: str) -> None:
        data = get_shift_summary(start_date, end_date)
        currency_symbol = current_currency_symbol()
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
                format_money(float(row["opening_balance"]), currency_symbol),
                format_money(float(row["expected_balance"]), currency_symbol)
                if row["expected_balance"] is not None
                else format_money(0, currency_symbol),
                row["status"],
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_payment(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_payment(start_date, end_date)
        currency_symbol = current_currency_symbol()
        
        self.report_table.setColumnCount(3)
        self.report_table.setHorizontalHeaderLabels([
            "Payment Method", "Transactions", "Total"
        ])
        
        self.report_table.setRowCount(len(data))
        for row_index, row in enumerate(data):
            values = [
                row["payment_method"],
                str(row["transaction_count"]),
                format_money(float(row["total_sales"]), currency_symbol),
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.report_table.setItem(row_index, column_index, item)

    def load_sales_by_product(self, start_date: str, end_date: str) -> None:
        data = get_sales_by_product(start_date, end_date)
        currency_symbol = current_currency_symbol()
        
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
                format_money(float(row["total_sales"]), currency_symbol),
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

            QMenu {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 0;
                padding: 0;
            }

            QMenu::item {
                padding: 8px 18px;
            }

            QMenu::item:selected {
                background: #E5E7EB;
            }

            #primaryButton {
                background: #2563EB;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 14px;
            }

            #primaryButton:hover {
                background: #1D4ED8;
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
            """ + MODERN_WIDGET_STYLESHEET
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_reports(current_user: dict) -> ReportsWindow:
    window = ReportsWindow(current_user)
    return window
