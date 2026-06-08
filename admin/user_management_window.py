from time import monotonic
from typing import Any, Callable

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from login import (
    add_user,
    get_all_roles,
    get_all_users,
    log_audit,
    refresh_store_users_from_cloud,
    set_user_active,
    soft_delete_user,
    update_user,
)
from ui.dialogs import confirm_delete
from ui.icon_manager import IconManager
from ui.loading import BlockingTaskRunner, USER_SYNC_TIMEOUT_MS
from ui.notifications import friendly_error
from ui.theme import build_modern_widget_stylesheet, THEME_DARK, THEME_LIGHT, get_theme_mode





def _polish_user_action_button(button, kind="neutral"):
    """Apply compact, centered styling for user-management action buttons."""
    try:
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtWidgets import QSizePolicy
    except Exception:
        return button

    palette = {
        "edit": ("#2563eb", "#eff6ff", "#bfdbfe", "#dbeafe"),
        "active": ("#ffffff", "#0f766e", "#0f766e", "#115e59"),
        "inactive": ("#46586A", "#f8fafc", "#cbd5e1", "#f1f5f9"),
        "delete": ("#e11d48", "#fff1f2", "#fecdd3", "#ffe4e6"),
        "neutral": ("#314154", "#f8fafc", "#cbd5e1", "#f1f5f9"),
    }
    color, bg, border, hover = palette.get(kind, palette["neutral"])
    selector = f"#{button.objectName()}" if button.objectName() else button.metaObject().className()
    button.setFixedSize(QSize(36, 36))
    button.setMinimumSize(QSize(36, 36))
    button.setMaximumSize(QSize(36, 36))
    button.setIconSize(QSize(17, 17))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    button.setStyleSheet(f"""
        {selector} {{
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
            color: {color};
            background: {bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 0;
            margin: 0;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
        }}
        {selector}:hover {{
            background: {hover};
            border-color: {color};
            color: {color};
        }}
        {selector}:pressed {{
            background: {border};
        }}
        {selector}:disabled {{
            color: #94a3b8;
            background: #f1f5f9;
            border-color: #e2e8f0;
        }}
    """)
    return button

def row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


class UserEditDialog(QDialog):
    def __init__(
        self,
        user: Any,
        roles: list[Any],
        save_callback: Callable[[dict[str, Any]], dict[str, object]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.user = user
        self.roles = roles
        self.save_callback = save_callback
        self.runner = BlockingTaskRunner(self, timeout_ms=USER_SYNC_TIMEOUT_MS)
        self.result_payload: dict[str, object] | None = None
        self.setWindowTitle("Edit User")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.create_ui()
        self.apply_styles()
        self.bind_user()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(13)

        title = IconManager.label("Edit User", "edit", "dialogTitle", icon_size=20)
        layout.addWidget(title)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Full name")
        self.role_combo = QComboBox()
        self.change_password_checkbox = QCheckBox("Change password")
        self.change_password_checkbox.setObjectName("changePasswordCheck")
        self.change_password_checkbox.toggled.connect(self.toggle_change_password_fields)
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("New password")
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm new password")
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        for label_text, widget in (
            ("Email", self.email_input),
            ("Full Name", self.full_name_input),
            ("Role", self.role_combo),
        ):
            label = QLabel(label_text)
            label.setObjectName("formLabel")
            layout.addWidget(label)
            layout.addWidget(widget)

        layout.addWidget(self.change_password_checkbox)

        self.new_password_label = QLabel("New Password")
        self.new_password_label.setObjectName("formLabel")
        layout.addWidget(self.new_password_label)
        layout.addWidget(self.new_password_input)

        self.confirm_password_label = QLabel("Confirm New Password")
        self.confirm_password_label.setObjectName("formLabel")
        layout.addWidget(self.confirm_password_label)
        layout.addWidget(self.confirm_password_input)
        self.toggle_change_password_fields(False)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("dialogFeedback")
        self.feedback_label.setWordWrap(True)
        layout.addWidget(self.feedback_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("neutralButton")
        cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("primaryButton")
        IconManager.apply_button(self.save_button, "save", IconManager.LIGHT)
        self.save_button.clicked.connect(self.save_user)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def bind_user(self) -> None:
        self.email_input.setText(str(row_value(self.user, "email") or row_value(self.user, "username") or ""))
        self.full_name_input.setText(str(row_value(self.user, "full_name") or ""))
        self.load_roles(int(row_value(self.user, "role_id") or 0))

    def load_roles(self, selected_role_id: int) -> None:
        self.role_combo.clear()
        for role in self.roles:
            role_id = int(row_value(role, "id") or 0)
            self.role_combo.addItem(str(row_value(role, "name") or ""), role_id)
            if role_id == selected_role_id:
                self.role_combo.setCurrentIndex(self.role_combo.count() - 1)
        if selected_role_id and self.role_combo.currentData() != selected_role_id:
            self.feedback_label.setText("Current role no longer exists. Please select a role.")

    def form_data(self) -> dict[str, Any]:
        return {
            "user_id": int(row_value(self.user, "id")),
            "email": self.email_input.text().strip(),
            "full_name": self.full_name_input.text().strip(),
            "role_id": self.role_combo.currentData(),
            "change_password": self.change_password_checkbox.isChecked(),
            "password": self.new_password_input.text() if self.change_password_checkbox.isChecked() else "",
            "confirm_password": self.confirm_password_input.text() if self.change_password_checkbox.isChecked() else "",
        }

    def toggle_change_password_fields(self, checked: bool) -> None:
        self.new_password_label.setVisible(checked)
        self.new_password_input.setVisible(checked)
        self.confirm_password_label.setVisible(checked)
        self.confirm_password_input.setVisible(checked)
        if not checked:
            self.new_password_input.clear()
            self.confirm_password_input.clear()

    def save_user(self) -> None:
        data = self.form_data()
        if not data["email"] or not data["full_name"]:
            self.feedback_label.setText("Please fill email and full name.")
            return
        if data["role_id"] is None:
            self.feedback_label.setText("Please select a role.")
            return
        if data["change_password"]:
            if not data["password"] or not data["confirm_password"]:
                self.feedback_label.setText("Please fill and confirm the new password.")
                return
            if data["password"] != data["confirm_password"]:
                self.feedback_label.setText("New password confirmation does not match.")
                return

        def on_success(result: dict[str, object]) -> None:
            self.result_payload = result
            self.accept()

        def on_error(error: Exception) -> None:
            self.feedback_label.setText(friendly_error(error))
            self.save_button.setEnabled(True)
            self.save_button.setText("Save")

        self.feedback_label.setText("")
        self.save_button.setEnabled(False)
        self.save_button.setText("Saving...")
        started = self.runner.start(
            lambda: self.save_callback(data),
            "Updating user...",
            on_success=on_success,
            on_error=on_error,
            timeout_message="Updating this user is taking too long. Please check the network and try again.",
        )
        if not started:
            self.save_button.setEnabled(True)
            self.save_button.setText("Save")
            self.feedback_label.setText("A user sync task is already running.")

    def apply_styles(self) -> None:
        mode = get_theme_mode()
        if mode == THEME_DARK:
            styles = """
            QDialog {
                background: #101820;
            }
            #dialogTitle {
                color: #F5F8FA;
                font-size: 20px;
                font-weight: 800;
            }
            #formLabel, #dialogFeedback {
                color: #C8D3DF;
                font-size: 12px;
                font-weight: 700;
            }
            #dialogFeedback {
                color: #EF4444;
            }
            #changePasswordCheck {
                color: #E6EDF3;
                font-size: 13px;
                font-weight: 800;
                spacing: 8px;
            }
            #changePasswordCheck::indicator {
                width: 16px;
                height: 16px;
            }
            QLineEdit, QComboBox {
                background: #1F2A37;
                border: 1px solid #314154;
                border-radius: 8px;
                padding: 9px 11px;
                color: #E6EDF3;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 800;
                padding: 10px 14px;
            }
            #primaryButton {
                background: #60A5FA;
            }
            #neutralButton {
                background: #46586A;
                color: #E6EDF3;
            }
            QPushButton:disabled {
                background: #46586A;
                color: #A7B3C2;
            }
            """
        else:
            styles = """
            QDialog {
                background: #EEF1F4;
            }
            #dialogTitle {
                color: #17212B;
                font-size: 20px;
                font-weight: 800;
            }
            #formLabel, #dialogFeedback {
                color: #64707D;
                font-size: 12px;
                font-weight: 700;
            }
            #dialogFeedback {
                color: #B91C1C;
            }
            #changePasswordCheck {
                color: #25313D;
                font-size: 13px;
                font-weight: 800;
                spacing: 8px;
            }
            #changePasswordCheck::indicator {
                width: 16px;
                height: 16px;
            }
            QLineEdit, QComboBox {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 9px 11px;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 800;
                padding: 10px 14px;
            }
            #primaryButton {
                background: #2563EB;
            }
            #neutralButton {
                background: #E2E8F0;
                color: #17212B;
            }
            QPushButton:disabled {
                background: #C8D3DF;
                color: #708195;
            }
            """
        self.setStyleSheet(styles + build_modern_widget_stylesheet())


class StatusToggle(QPushButton):
    def __init__(self, checked: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 28)
        self.setText("")
        # Reset CSS để tránh padding thừa kế từ QPushButton gây lệch layout ô
        self.setStyleSheet("""
            QPushButton {
                min-width: 52px;
                max-width: 52px;
                min-height: 28px;
                max-height: 28px;
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
        """)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        track = QRectF(1, 2, width - 2, height - 4)
        knob_size = height - 8
        knob_x = width - knob_size - 5 if self.isChecked() else 5
        knob_y = 4
        track_color = QColor("#0F766E") if self.isChecked() else QColor("#E2E8F0")
        track_border = QColor("#0D9488") if self.isChecked() else QColor("#C8D3DF")
        symbol_color = QColor("#FFFFFF") if self.isChecked() else QColor("#708195")
        knob_shadow = QColor(15, 23, 42, 28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        painter.setPen(QPen(track_border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_shadow)
        painter.drawEllipse(QRectF(knob_x, knob_y + 1, knob_size, knob_size))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_size, knob_size))

        painter.setPen(QPen(symbol_color, 2))
        if self.isChecked():
            painter.drawLine(13, 15, 17, 19)
            painter.drawLine(17, 19, 24, 10)
        else:
            painter.drawLine(width - 18, 11, width - 11, 18)
            painter.drawLine(width - 11, 11, width - 18, 18)


class UserManagementWindow(QWidget):
    data_changed = pyqtSignal()
    sync_requested = pyqtSignal(object)

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.last_sync_request_at = 0.0
        self.highlight_user_id: int | None = None
        self.highlight_user_email = ""
        self.roles: list[Any] = []
        self.user_sync_runner = BlockingTaskRunner(self, timeout_ms=USER_SYNC_TIMEOUT_MS)
        self.create_ui()
        self.load_roles()
        self.load_users()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(IconManager.label("User Management", "users", "titleLabel", icon_size=20))
        subtitle = QLabel("Create users and manage store access")
        subtitle.setObjectName("subtitleLabel")
        header.addWidget(subtitle)
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(18)
        content.addWidget(self.create_form_panel())
        content.addWidget(self.create_table_panel(), 1)
        layout.addLayout(content, 1)
        self.create_toast_label()

    def create_form_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(360)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)
        layout.addWidget(IconManager.label("Create User", "user", "sectionLabel"))

        self.create_hint_label = QLabel("Create a new store employee account.")
        self.create_hint_label.setObjectName("helperLabel")
        self.create_hint_label.setWordWrap(True)
        layout.addWidget(self.create_hint_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter email")
        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Enter full name")
        self.role_combo = QComboBox()
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm password")
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        for label_text, widget in (
            ("Email", self.email_input),
            ("Full Name", self.fullname_input),
            ("Role", self.role_combo),
            ("Password", self.password_input),
            ("Confirm Password", self.confirm_password_input),
        ):
            label = QLabel(label_text)
            label.setObjectName("formLabel")
            layout.addWidget(label)
            layout.addWidget(widget)

        self.add_button = QPushButton("Create User")
        IconManager.apply_button(self.add_button, "add", IconManager.LIGHT)
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_user_action)
        layout.addWidget(self.add_button)

        self.clear_button = QPushButton("Clear")
        IconManager.apply_button(self.clear_button, "clear", IconManager.DARK)
        self.clear_button.setObjectName("neutralButton")
        self.clear_button.clicked.connect(self.clear_create_form)
        layout.addWidget(self.clear_button)
        layout.addStretch(1)
        return panel

    def create_table_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(IconManager.label("Users", "users", "sectionLabel"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search users...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_users)
        layout.addWidget(self.search_input)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["Email", "Full Name", "Role", "Status", "Created", "Actions"])
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setShowGrid(False)
        self.users_table.verticalHeader().setVisible(False)

        header = self.users_table.horizontalHeader()
        header.setMinimumSectionSize(82)
        
        # Cột 0 (Email) tự co giãn, cột 5 (Actions) tự ôm nội dung nút
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        
        self.users_table.setColumnWidth(1, 160)
        self.users_table.setColumnWidth(5, 184)
        self.users_table.verticalHeader().setDefaultSectionSize(52)
        layout.addWidget(self.users_table, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        return panel

    def create_toast_label(self) -> None:
        self.toast_label = QLabel(self)
        self.toast_label.setObjectName("userToast")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.setWordWrap(True)
        self.toast_label.hide()

    def load_roles(self) -> None:
        selected_role_id = self.role_combo.currentData() if hasattr(self, "role_combo") else None
        self.roles = get_all_roles()
        self.role_combo.clear()
        for role in self.roles:
            role_id = int(row_value(role, "id") or 0)
            self.role_combo.addItem(str(row_value(role, "name") or ""), role_id)
            if selected_role_id == role_id:
                self.role_combo.setCurrentIndex(self.role_combo.count() - 1)
        if selected_role_id is None:
            self.role_combo.setCurrentIndex(-1)

    def load_users(self) -> None:
        keyword = self.search_input.text().strip().lower()
        all_users = get_all_users()
        users = [
            user for user in all_users
            if not keyword
            or keyword in str(row_value(user, "email") or row_value(user, "username") or "").lower()
            or keyword in str(row_value(user, "full_name") or "").lower()
            or keyword in str(row_value(user, "role_name") or "").lower()
            or keyword in ("active" if row_value(user, "active") else "inactive")
        ]

        self.users_table.setRowCount(len(users))
        highlighted_row = -1
        for row_index, user in enumerate(users):
            status = "Active" if row_value(user, "active") else "Inactive"
            values = (
                row_value(user, "email") or row_value(user, "username") or "",
                row_value(user, "full_name") or "",
                row_value(user, "role_name") or "None",
                status,
                str(row_value(user, "created_at") or "")[:19],
            )
            highlighted = self.user_matches_highlight(user)
            if highlighted:
                highlighted_row = row_index
            for column_index, value in enumerate(values):
                alignment = Qt.AlignmentFlag.AlignCenter if column_index in {2, 3} else (
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                item = self.make_table_item(str(value), alignment)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(row_value(user, "id")))
                if column_index == 3:
                    item.setForeground(QColor("#0F766E" if row_value(user, "active") else "#B91C1C"))
                if highlighted:
                    item.setBackground(QColor("#DBEAFE"))
                self.users_table.setItem(row_index, column_index, item)
            self.users_table.setCellWidget(row_index, 5, self.create_actions_widget(user))

        if highlighted_row >= 0:
            first_item = self.users_table.item(highlighted_row, 0)
            if first_item is not None:
                self.users_table.scrollToItem(first_item)

        if keyword and not users:
            self.set_status(f"No users match '{keyword}'.")
        elif not all_users:
            self.set_status("No users in this store yet.")
        else:
            suffix = "user" if len(users) == 1 else "users"
            self.set_status(f"{len(users)} {suffix} shown.")

    def create_actions_widget(self, user: Any) -> QWidget:
        row = QWidget()
        row.setObjectName("actionsCell")
        row.setFixedSize(184, 52)
        row.setStyleSheet("""
            QWidget#actionsCell {
                background: transparent;
                border: none;
            }
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        edit_button = self.icon_action_button("Edit user", "edit", "editIconButton")
        _polish_user_action_button(edit_button, "edit")
        edit_button.clicked.connect(lambda _checked=False, u=user: self.open_edit_dialog(u))
        
        active = bool(row_value(user, "active"))
        toggle_button = StatusToggle(active)
        toggle_button.setToolTip("Disable user" if active else "Enable user")
        toggle_button.clicked.connect(lambda _checked=False, u=user, b=toggle_button: self.toggle_user_active(u, b))
        
        delete_button = self.icon_action_button("Delete user", "delete", "deleteIconButton")
        _polish_user_action_button(delete_button, "delete")
        delete_button.clicked.connect(lambda _checked=False, u=user: self.soft_delete_user_action(u))

        layout.addWidget(edit_button)
        layout.addWidget(toggle_button)
        layout.addWidget(delete_button)
        
        return row

    def icon_action_button(self, tooltip: str, icon_key: str, object_name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setFixedSize(36, 36)
        button.setToolTip(tooltip)
        button.setAutoRaise(False)
        icon_color = "#E11D48" if object_name == "deleteIconButton" else "#2563EB"
        button.setIcon(IconManager.icon(icon_key, icon_color))
        button.setIconSize(QSize(17, 17))
        return button

    def make_table_item(self, value: str, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setTextAlignment(alignment)
        return item

    def reload_data(self) -> None:
        self.load_users()

    def refresh_users_from_cloud(self) -> None:
        self.set_status("Refreshing users...")
        try:
            refresh_store_users_from_cloud()
        except Exception as error:
            message = friendly_error(error)
            self.set_status(message, is_error=True)
            self.show_toast(message, is_error=True)
            return
        self.load_users()
        self.set_status("Users updated.")
        self.show_toast("Users updated.")

    def request_user_sync(self, force: bool = False) -> None:
        now = monotonic()
        if not force and now - self.last_sync_request_at < 60:
            return
        self.last_sync_request_at = now
        self.set_status("Refreshing users...")
        self.sync_requested.emit({"users"})

    def add_user_action(self) -> None:
        email = self.email_input.text().strip()
        full_name = self.fullname_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        role_id = self.role_combo.currentData()

        if not email or not full_name or not password or not confirm_password:
            self.set_status("Please fill email, full name, password, and confirm password.", is_error=True)
            return
        if password != confirm_password:
            self.set_status("Password confirmation does not match.", is_error=True)
            return
        if role_id is None:
            self.set_status("Please select a role.", is_error=True)
            return

        def task() -> dict[str, object]:
            user_id = add_user(email, password, full_name, int(role_id))
            log_audit(self.current_user["id"], "CREATE_USER", "users", user_id, None, f"email: {email}")
            refresh_store_users_from_cloud()
            return {"user_id": user_id, "email": email}

        self.run_user_action(
            action="create",
            message="Creating user...",
            task=task,
            success_message=f"User created: {email}",
            on_success=lambda result: self.after_user_changed(result, clear_create=True),
        )

    def open_edit_dialog(self, user: Any) -> None:
        def save_callback(data: dict[str, Any]) -> dict[str, object]:
            password = str(data["password"] or "") if data.get("change_password") else ""
            password = password or None
            update_user(
                int(data["user_id"]),
                str(data["email"]),
                str(data["full_name"]),
                int(data["role_id"]),
                password,
            )
            log_audit(self.current_user["id"], "UPDATE_USER", "users", int(data["user_id"]), None, f"email: {data['email']}")
            refresh_store_users_from_cloud()
            return {"user_id": int(data["user_id"]), "email": str(data["email"])}

        dialog = UserEditDialog(user, self.roles or get_all_roles(), save_callback, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_payload is not None:
            self.after_user_changed(dialog.result_payload, clear_create=False)
            self.set_status("User updated.")
            self.show_toast(f"User updated: {dialog.result_payload.get('email')}")

    def toggle_user_active(self, user: Any, toggle_button: StatusToggle | None = None) -> None:
        user_id = int(row_value(user, "id"))
        email = str(row_value(user, "email") or row_value(user, "username") or "")
        active = bool(row_value(user, "active"))
        if toggle_button is not None:
            toggle_button.setChecked(active)
        make_active = not active
        verb = "Enabling" if make_active else "Disabling"

        def task() -> dict[str, object]:
            set_user_active(user_id, make_active, int(self.current_user["id"]))
            log_audit(
                self.current_user["id"],
                "ENABLE_USER" if make_active else "DISABLE_USER",
                "users",
                user_id,
                None,
                f"email: {email}",
            )
            refresh_store_users_from_cloud()
            return {"user_id": user_id, "email": email}

        self.run_user_action(
            action="toggle",
            message=f"{verb} user...",
            task=task,
            success_message=f"User {'enabled' if make_active else 'disabled'}: {email}",
            on_success=lambda result: self.after_user_changed(result, clear_create=False),
        )

    def soft_delete_user_action(self, user: Any) -> None:
        user_id = int(row_value(user, "id"))
        email = str(row_value(user, "email") or row_value(user, "username") or "")
        if not confirm_delete(self, "Delete this user? Sales history and audit records will be kept."):
            return

        def task() -> dict[str, object]:
            soft_delete_user(user_id, int(self.current_user["id"]))
            log_audit(self.current_user["id"], "DELETE_USER", "users", user_id, None, f"email: {email}")
            refresh_store_users_from_cloud()
            return {"user_id": user_id, "email": email}

        self.run_user_action(
            action="delete",
            message="Deleting user...",
            task=task,
            success_message=f"User deleted: {email}",
            on_success=lambda result: self.after_user_changed(result, clear_create=False),
        )

    def run_user_action(
        self,
        action: str,
        message: str,
        task: Callable[[], dict[str, object]],
        success_message: str,
        on_success: Callable[[dict[str, object]], None],
    ) -> None:
        def handle_success(result: dict[str, object]) -> None:
            self.set_user_action_busy(None)
            on_success(result)
            self.set_status(success_message)
            self.show_toast(success_message)

        def handle_error(error: Exception) -> None:
            self.set_user_action_busy(None)
            if action != "create":
                self.load_users()
            message = friendly_error(error)
            self.set_status(message, is_error=True)
            self.show_toast(message, is_error=True)

        self.set_status(message)
        self.set_user_action_busy(action)
        started = self.user_sync_runner.start(
            task,
            message,
            on_success=handle_success,
            on_error=handle_error,
            timeout_message=f"{message.rstrip('.')} is taking too long. Please check the network and try again.",
        )
        if not started:
            self.set_user_action_busy(None)
            self.set_status("A user sync task is already running.", is_error=True)

    def after_user_changed(self, result: dict[str, object], clear_create: bool) -> None:
        self.highlight_user_id = int(result.get("user_id") or 0) or None
        self.highlight_user_email = str(result.get("email") or "")
        if clear_create:
            self.clear_create_form()
        self.load_users()
        self.data_changed.emit()
        self.sync_requested.emit({"users"})
        self.clear_highlight_later()

    def set_user_action_busy(self, action: str | None) -> None:
        busy = action is not None
        self.email_input.setEnabled(not busy)
        self.fullname_input.setEnabled(not busy)
        self.role_combo.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.confirm_password_input.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.users_table.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.add_button.setText("Creating..." if action == "create" else "Create User")

    def clear_create_form(self) -> None:
        self.email_input.clear()
        self.fullname_input.clear()
        self.password_input.clear()
        self.confirm_password_input.clear()
        self.role_combo.setCurrentIndex(-1)
        self.email_input.setFocus()

    def set_status(self, message: str, is_error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", is_error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def show_toast(self, message: str, is_error: bool = False) -> None:
        self.toast_label.setText(message)
        self.toast_label.setProperty("error", is_error)
        self.toast_label.style().unpolish(self.toast_label)
        self.toast_label.style().polish(self.toast_label)
        self.toast_label.adjustSize()
        self.toast_label.setFixedWidth(min(max(self.toast_label.width() + 26, 260), 440))
        self.position_toast()
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(3000, self.toast_label.hide)

    def position_toast(self) -> None:
        if not hasattr(self, "toast_label"):
            return
        margin = 24
        self.toast_label.adjustSize()
        self.toast_label.move(max(margin, self.width() - self.toast_label.width() - margin), margin)

    def user_matches_highlight(self, user: Any) -> bool:
        if self.highlight_user_id is not None:
            try:
                if int(row_value(user, "id")) == self.highlight_user_id:
                    return True
            except (TypeError, ValueError):
                pass
        email = str(row_value(user, "email") or row_value(user, "username") or "").strip().lower()
        return bool(self.highlight_user_email and email == self.highlight_user_email.lower())

    def clear_highlight_later(self) -> None:
        QTimer.singleShot(3500, self.clear_highlight)

    def clear_highlight(self) -> None:
        if self.highlight_user_id is None and not self.highlight_user_email:
            return
        self.highlight_user_id = None
        self.highlight_user_email = ""
        self.load_users()

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
                font-weight: 800;
            }
            #subtitleLabel, #helperLabel, #statusLabel, #formLabel {
                color: #64707D;
                font-size: 12px;
                font-weight: 700;
            }
            #sectionLabel {
                color: #25313D;
                font-size: 15px;
                font-weight: 800;
            }
            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
            }
            #statusLabel[error="true"] {
                color: #B91C1C;
            }
            #userToast {
                background: #ECFDF5;
                border: 1px solid #A7F3D0;
                border-radius: 8px;
                color: #047857;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 14px;
            }
            #userToast[error="true"] {
                background: #FEF2F2;
                border: 1px solid #FECACA;
                color: #B91C1C;
            }
            QLineEdit, QComboBox {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 10px 12px;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 800;
                padding: 9px 12px;
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
            #editIconButton, #deleteIconButton {
                background: #F8FAFC;
                border: 1px solid #C8D3DF;
                border-radius: 8px;
                padding: 0;
            }
            #editIconButton:hover {
                background: #E0F2FE;
                border-color: #7DD3FC;
            }
            #deleteIconButton {
                background: #FEF2F2;
                border-color: #FECACA;
            }
            #deleteIconButton:hover {
                background: #FEE2E2;
                border-color: #FCA5A5;
            }
            #actionsCell {
                background: transparent;
            }
            QPushButton:disabled {
                background: #C8D3DF;
                color: #708195;
            }
            QTableWidget {
                background: #FFFFFF;
                border: 1px solid #D9E3EE;
                border-radius: 8px;
                alternate-background-color: #F8FAFC;
                gridline-color: transparent;
                selection-background-color: #E0F2FE;
                selection-color: #101820;
            }
            QHeaderView::section {
                background: #F1F5F9;
                border: none;
                border-bottom: 1px solid #D9E3EE;
                color: #1F2A37;
                font-weight: 800;
                padding: 11px 10px;
            }
            QTableWidget::item {
                border-bottom: 1px solid #EDF2F7;
                padding: 8px 10px;
            }
            """ + build_modern_widget_stylesheet()
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()
        QTimer.singleShot(0, self.request_user_sync)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_toast()


def create_user_management(current_user: dict) -> UserManagementWindow:
    return UserManagementWindow(current_user)
