from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
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

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.selected_user_id: int | None = None
        self.create_ui()
        self.load_users()
        self.load_roles()

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

        refresh_button = QPushButton("Sync Users")
        IconManager.apply_button(refresh_button, "refresh", IconManager.LIGHT)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_users_from_cloud)
        header_layout.addWidget(refresh_button)
        
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
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
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
        
        self.delete_button = QPushButton("Delete User")
        IconManager.apply_button(self.delete_button, "delete", IconManager.LIGHT)
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_user_action)
        
        self.clear_button = QPushButton("Clear")
        IconManager.apply_button(self.clear_button, "clear", IconManager.LIGHT)
        self.clear_button.setObjectName("neutralButton")
        self.clear_button.clicked.connect(self.clear_form)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
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
            ["ID", "Email", "Full Name", "Role", "Active"]
        )
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(False)
        self.users_table.verticalHeader().setVisible(False)
        
        header = self.users_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.users_table.setColumnWidth(1, 150)
        self.users_table.setColumnWidth(2, 180)
        
        self.users_table.itemSelectionChanged.connect(self.load_selected_user)
        
        layout.addWidget(self.users_table, 1)
        
        return panel

    def load_users(self) -> None:
        keyword = self.search_input.text().strip()
        users = get_all_users()
        
        if keyword:
            users = [
                u for u in users
                if keyword.lower() in str(u["email"] or u["username"]).lower()
                or keyword.lower() in str(u["full_name"]).lower()
            ]
        
        self.users_table.setRowCount(len(users))
        for row_index, user in enumerate(users):
            values = [
                str(user["id"]),
                user["email"] or user["username"] or "",
                user["full_name"] or "",
                user["role_name"] or "None",
                "Yes" if user["active"] else "No",
            ]
            
            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column_index == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, int(user["id"]))
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.users_table.setItem(row_index, column_index, table_item)

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
            QMessageBox.warning(self, "Sync Error", str(error))
            return
        self.load_users()
        QMessageBox.information(self, "Success", "Users synced from Supabase.")

    def load_selected_user(self) -> None:
        selected_row = self.users_table.currentRow()
        if selected_row < 0:
            return
        
        self.selected_user_id = int(
            self.users_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        )
        
        users = get_all_users()
        user = next((u for u in users if u["id"] == self.selected_user_id), None)
        
        if user:
            self.username_input.setText(user["email"] or user["username"])
            self.fullname_input.setText(user["full_name"])
            self.role_combo.setCurrentText(user["role_name"] or "")
            self.password_input.clear()
            self.password_input.setPlaceholderText("Leave blank to keep current")

    def add_user_action(self) -> None:
        email = self.username_input.text().strip()
        full_name = self.fullname_input.text().strip()
        password = self.password_input.text()
        role_id = self.role_combo.currentData()
        
        if not email or not full_name or not password:
            QMessageBox.warning(self, "Validation Error", "Please fill all fields")
            return
        
        if role_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a role")
            return
        
        try:
            user_id = add_user(email, password, full_name, role_id)
            log_audit(self.current_user["id"], "CREATE_USER", "users", user_id, None, f"email: {email}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "User added successfully")

    def update_user_action(self) -> None:
        if self.selected_user_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a user to update")
            return
        
        email = self.username_input.text().strip()
        full_name = self.fullname_input.text().strip()
        password = self.password_input.text() or None
        role_id = self.role_combo.currentData()
        
        if not email or not full_name:
            QMessageBox.warning(self, "Validation Error", "Please fill required fields")
            return
        
        if role_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a role")
            return
        
        try:
            update_user(self.selected_user_id, email, full_name, role_id, password)
            log_audit(self.current_user["id"], "UPDATE_USER", "users", self.selected_user_id, None, f"email: {email}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "User updated successfully")

    def delete_user_action(self) -> None:
        if self.selected_user_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a user to delete")
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
            QMessageBox.warning(self, "Error", str(e))
            return
        
        self.clear_form()
        self.load_users()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "User deactivated successfully")

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

            #formLabel {
                color: #64707D;
                font-size: 12px;
                font-weight: 600;
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
                background: #6B7280;
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


def create_user_management(current_user: dict) -> UserManagementWindow:
    window = UserManagementWindow(current_user)
    return window
