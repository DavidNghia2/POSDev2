from time import monotonic

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from login import (
    add_user,
    delete_user,
    get_all_roles,
    get_all_users,
    log_audit,
    refresh_store_users_from_cloud,
    update_user,
)
from ui.dialogs import confirm_delete
from ui.icon_manager import IconManager
from ui.theme import MODERN_WIDGET_STYLESHEET


class UserManagementWindow(QWidget):
    data_changed = pyqtSignal()
    sync_requested = pyqtSignal(object)

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.selected_user_id: int | None = None
        self.last_sync_request_at = 0.0
        self.last_status_message = ""
        self.create_ui()
        self.load_users()
        self.load_roles()
        self.update_form_mode()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = IconManager.label("User Management", "users", "titleLabel", icon_size=20)
        
        subtitle_label = QLabel("Manage users and access permissions")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Content split
        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        
        # Left panel - User form
        form_panel = self.create_form_panel()
        
        # Right panel - User list
        table_panel = self.create_table_panel()
        
        content_layout.addWidget(form_panel)
        content_layout.addWidget(table_panel, 1)
        
        layout.addLayout(content_layout, 1)

    def create_form_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(360)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)
        
        section_label = IconManager.label("User Details", "user", "sectionLabel")
        layout.addWidget(section_label)

        self.form_mode_label = QLabel("New user")
        self.form_mode_label.setObjectName("helperLabel")
        layout.addWidget(self.form_mode_label)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Email
        username_label = QLabel("Email")
        username_label.setObjectName("formLabel")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter email")
        
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_input)
        
        # Full name
        fullname_label = QLabel("Full Name")
        fullname_label.setObjectName("formLabel")
        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Enter full name")
        
        form_layout.addWidget(fullname_label)
        form_layout.addWidget(self.fullname_input)
        
        # Role
        role_label = QLabel("Role")
        role_label.setObjectName("formLabel")
        self.role_combo = QComboBox()
        self.role_combo.setPlaceholderText("Select role")
        
        form_layout.addWidget(role_label)
        form_layout.addWidget(self.role_combo)
        
        # Password
        password_label = QLabel("Password")
        password_label.setObjectName("formLabel")
        self.password_label = password_label
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Required for new user")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.add_button = QPushButton("Add User")
        IconManager.apply_button(self.add_button, "add", IconManager.LIGHT)
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_user_action)
        
        self.update_button = QPushButton("Update User")
        IconManager.apply_button(self.update_button, "edit", IconManager.LIGHT)
        self.update_button.setObjectName("secondaryButton")
        self.update_button.clicked.connect(self.update_user_action)

        self.clear_button = QPushButton("Clear")
        IconManager.apply_button(self.clear_button, "clear", IconManager.LIGHT)
        self.clear_button.setObjectName("neutralButton")
        self.clear_button.clicked.connect(self.clear_form)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.clear_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()

        self.delete_button = QPushButton("Deactivate User")
        IconManager.apply_button(self.delete_button, "delete", IconManager.LIGHT)
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_user_action)
        layout.addWidget(self.delete_button)
        
        return panel

    def create_table_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        section_label = IconManager.label("Users", "users", "sectionLabel")
        layout.addWidget(section_label)
        
        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search users...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_users)
        layout.addWidget(self.search_input)
        
        # Table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(
            ["Email", "Full Name", "Role", "Status", "Created"]
        )
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(False)
        self.users_table.verticalHeader().setVisible(False)
        
        header = self.users_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.users_table.setColumnWidth(0, 220)
        self.users_table.verticalHeader().setDefaultSectionSize(42)
        
        self.users_table.itemSelectionChanged.connect(self.load_selected_user)
        
        layout.addWidget(self.users_table, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        
        return panel

    def load_users(self) -> None:
        keyword = self.search_input.text().strip()
        all_users = get_all_users()
        users = all_users
        
        if keyword:
            users = [
                u for u in users
                if keyword.lower() in str(u["email"] or u["username"]).lower()
                or keyword.lower() in str(u["full_name"]).lower()
                or keyword.lower() in str(u["role_name"] or "").lower()
                or keyword.lower() in ("active" if u["active"] else "inactive")
            ]
        
        self.users_table.setRowCount(len(users))
        for row_index, user in enumerate(users):
            status = "Active" if user["active"] else "Inactive"
            values = (
                user["email"] or user["username"] or "",
                user["full_name"] or "",
                user["role_name"] or "None",
                status,
                str(user["created_at"] or "")[:19],
            )

            for column_index, value in enumerate(values):
                alignment = (
                    Qt.AlignmentFlag.AlignCenter
                    if column_index in {2, 3}
                    else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                table_item = self.make_table_item(str(value), alignment)
                if column_index == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, int(user["id"]))
                if column_index == 3:
                    table_item.setForeground(QColor("#0F766E" if user["active"] else "#B91C1C"))
                self.users_table.setItem(row_index, column_index, table_item)

        if keyword and not users:
            self.set_status(f"No users match '{keyword}'.")
        elif not all_users:
            self.set_status("No users in this store yet.")
        else:
            suffix = "user" if len(users) == 1 else "users"
            self.set_status(f"{len(users)} {suffix} shown.")

    def make_table_item(self, value: str, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        table_item = QTableWidgetItem(value)
        table_item.setTextAlignment(alignment)
        return table_item

    def load_roles(self) -> None:
        roles = get_all_roles()
        self.role_combo.clear()
        for role in roles:
            self.role_combo.addItem(role["name"], role["id"])

    def reload_data(self) -> None:
        self.load_roles()
        self.load_users()

    def refresh_users_from_cloud(self) -> None:
        try:
            refresh_store_users_from_cloud()
        except Exception as error:
            self.set_status(f"Could not refresh users: {error}", is_error=True)
            return
        self.load_users()
        self.set_status("Users updated.")

    def request_user_sync(self, force: bool = False) -> None:
        now = monotonic()
        if not force and now - self.last_sync_request_at < 60:
            return
        self.last_sync_request_at = now
        self.sync_requested.emit({"users"})

    def set_status(self, message: str, is_error: bool = False) -> None:
        self.last_status_message = message
        self.status_label.setText(message)
        self.status_label.setProperty("error", is_error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def update_form_mode(self) -> None:
        editing = self.selected_user_id is not None
        self.form_mode_label.setText(
            "Editing selected user. Leave password blank to keep it unchanged."
            if editing
            else "Create a new store user."
        )
        self.password_label.setText("New Password" if editing else "Password")
        self.password_input.setPlaceholderText(
            "Leave blank to keep current" if editing else "Required for new user"
        )
        self.add_button.setEnabled(not editing)
        self.update_button.setEnabled(editing)
        self.delete_button.setEnabled(editing)

    def load_selected_user(self) -> None:
        selected_row = self.users_table.currentRow()
        if selected_row < 0:
            return

        id_item = self.users_table.item(selected_row, 0)
        if id_item is None:
            return
        self.selected_user_id = int(id_item.data(Qt.ItemDataRole.UserRole))
        
        users = get_all_users()
        user = next((u for u in users if u["id"] == self.selected_user_id), None)
        
        if user:
            self.username_input.setText(user["email"] or user["username"])
            self.fullname_input.setText(user["full_name"])
            self.role_combo.setCurrentText(user["role_name"] or "")
            self.password_input.clear()
            self.update_form_mode()

    def add_user_action(self) -> None:
        email = self.username_input.text().strip()
        full_name = self.fullname_input.text().strip()
        password = self.password_input.text()
        role_id = self.role_combo.currentData()
        
        if not email or not full_name or not password:
            self.set_status("Please fill email, full name, and password.", is_error=True)
            return
        
        if role_id is None:
            self.set_status("Please select a role.", is_error=True)
            return
        
        try:
            user_id = add_user(email, password, full_name, role_id)
            log_audit(self.current_user["id"], "CREATE_USER", "users", user_id, None, f"email: {email}")
        except Exception as e:
            self.set_status(str(e), is_error=True)
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        self.sync_requested.emit({"users"})
        self.set_status("User added.")

    def update_user_action(self) -> None:
        if self.selected_user_id is None:
            self.set_status("Select a user to update.", is_error=True)
            return
        
        email = self.username_input.text().strip()
        full_name = self.fullname_input.text().strip()
        password = self.password_input.text() or None
        role_id = self.role_combo.currentData()
        
        if not email or not full_name:
            self.set_status("Please fill email and full name.", is_error=True)
            return
        
        if role_id is None:
            self.set_status("Please select a role.", is_error=True)
            return
        
        try:
            update_user(self.selected_user_id, email, full_name, role_id, password)
            log_audit(self.current_user["id"], "UPDATE_USER", "users", self.selected_user_id, None, f"email: {email}")
        except Exception as e:
            self.set_status(str(e), is_error=True)
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        self.sync_requested.emit({"users"})
        self.set_status("User updated.")

    def delete_user_action(self) -> None:
        if self.selected_user_id is None:
            self.set_status("Select a user to deactivate.", is_error=True)
            return
        
        if not confirm_delete(
            self,
            "Deactivate this user? Their sales history and audit records will be kept.",
        ):
            return
        
        try:
            delete_user(self.selected_user_id, self.current_user["id"])
            log_audit(self.current_user["id"], "DELETE_USER", "users", self.selected_user_id)
        except Exception as e:
            self.set_status(str(e), is_error=True)
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        self.sync_requested.emit({"users"})
        self.set_status("User deactivated.")

    def clear_form(self) -> None:
        self.selected_user_id = None
        self.users_table.blockSignals(True)
        self.users_table.clearSelection()
        self.users_table.setCurrentCell(-1, -1)
        self.users_table.blockSignals(False)
        
        self.username_input.clear()
        self.fullname_input.clear()
        self.password_input.clear()
        self.role_combo.setCurrentIndex(-1)
        self.update_form_mode()
        self.username_input.setFocus()

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
                font-size: 24px;
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

            #formLabel {
                color: #64707D;
                font-size: 12px;
                font-weight: 600;
            }

            #helperLabel, #statusLabel {
                color: #64707D;
                font-size: 12px;
                font-weight: 600;
            }

            #statusLabel[error="true"] {
                color: #B91C1C;
            }

            QLineEdit, QComboBox {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 10px 12px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #2563EB;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 12px 14px;
            }

            #primaryButton {
                background: #2563EB;
            }

            #secondaryButton {
                background: #0F766E;
            }

            #dangerButton {
                background: #DC2626;
            }
            
            #neutralButton {
                background: #E2E8F0;
                color: #17212B;
            }

            QPushButton:disabled {
                background: #CBD5E1;
                color: #64748B;
            }

            QPushButton:pressed {
                padding-top: 13px;
                padding-bottom: 11px;
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
        QTimer.singleShot(0, self.request_user_sync)


def create_user_management(current_user: dict) -> UserManagementWindow:
    window = UserManagementWindow(current_user)
    return window
