from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from login import get_audit_logs


def row_value(row, key: str, default: str = ""):
    return row[key] if key in row.keys() and row[key] is not None else default


class AuditLogsWindow(QWidget):
    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.create_ui()
        self.load_logs()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = QLabel("Audit Logs")
        title_label.setObjectName("titleLabel")
        
        subtitle_label = QLabel("System activity and user actions")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.load_logs)
        header_layout.addWidget(self.refresh_button)
        
        layout.addLayout(header_layout)
        
        # Filters
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(12)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        
        # Action filter
        filters_layout.addWidget(QLabel("Action:"))
        self.action_filter = QComboBox()
        self.action_filter.addItems(["All", "LOGIN", "CREATE_USER", "UPDATE_USER", "DELETE_USER", 
                                     "CREATE_REGISTER", "UPDATE_REGISTER", "DELETE_REGISTER",
                                     "CREATE_SALE", "UPDATE_SALE", "DELETE_SALE"])
        self.action_filter.currentIndexChanged.connect(self.load_logs)
        filters_layout.addWidget(self.action_filter)
        
        # User filter
        filters_layout.addWidget(QLabel("User:"))
        self.user_filter = QLineEdit()
        self.user_filter.setPlaceholderText("Search user...")
        self.user_filter.setClearButtonEnabled(True)
        self.user_filter.textChanged.connect(self.load_logs)
        filters_layout.addWidget(self.user_filter)
        
        # Limit
        filters_layout.addWidget(QLabel("Show:"))
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["50", "100", "200", "500"])
        self.limit_combo.setCurrentIndex(1)
        self.limit_combo.currentIndexChanged.connect(self.load_logs)
        filters_layout.addWidget(self.limit_combo)
        
        filters_layout.addStretch()
        
        layout.addLayout(filters_layout)
        
        # Log table
        log_panel = QFrame()
        log_panel.setObjectName("panel")
        
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 18, 18, 18)
        log_layout.setSpacing(12)
        
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(6)
        self.logs_table.setHorizontalHeaderLabels([
            "ID", "Timestamp", "User", "Action", "Table", "Details"
        ])
        self.logs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.logs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.logs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.logs_table.setAlternatingRowColors(True)
        self.logs_table.setShowGrid(False)
        self.logs_table.verticalHeader().setVisible(False)
        
        header = self.logs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.logs_table.setColumnWidth(0, 60)
        self.logs_table.setColumnWidth(1, 160)
        self.logs_table.setColumnWidth(2, 120)
        self.logs_table.setColumnWidth(3, 120)
        self.logs_table.setColumnWidth(4, 120)
        
        log_layout.addWidget(self.logs_table, 1)
        
        layout.addWidget(log_panel, 1)

    def load_logs(self) -> None:
        action = self.action_filter.currentText()
        user_keyword = self.user_filter.text().strip()
        limit = int(self.limit_combo.currentText())
        
        all_logs = get_audit_logs(limit)
        
        # Apply filters
        filtered_logs = []
        for log in all_logs:
            if action != "All" and log["action"] != action:
                continue
            if user_keyword:
                username = str(row_value(log, "username")).lower()
                full_name = str(row_value(log, "full_name")).lower()
                if user_keyword.lower() not in username and user_keyword.lower() not in full_name:
                    continue
            filtered_logs.append(log)
        
        self.logs_table.setRowCount(len(filtered_logs))
        for row_index, log in enumerate(filtered_logs):
            values = [
                str(log["id"]),
                log["created_at"][:19] if log["created_at"] else "",
                row_value(log, "full_name", "System"),
                log["action"],
                log["table_name"] or "",
                self.format_details(log),
            ]
            
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.logs_table.setItem(row_index, column_index, item)

    def format_details(self, log: dict) -> str:
        details = []
        
        if row_value(log, "record_id", None):
            details.append(f"ID: {log['record_id']}")
        
        old_vals = row_value(log, "old_values", None)
        new_vals = row_value(log, "new_values", None)
        
        if old_vals:
            details.append(f"From: {old_vals[:50]}")
        if new_vals:
            details.append(f"To: {new_vals[:50]}")
        
        return " | ".join(details) if details else "-"

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

            QLineEdit, QComboBox {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 8px 12px;
                min-width: 100px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #2563EB;
            }

            #refreshButton {
                background: #2563EB;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px 16px;
            }

            #refreshButton:hover {
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
            """
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_audit_logs(current_user: dict) -> AuditLogsWindow:
    window = AuditLogsWindow(current_user)
    return window
