from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
    add_register,
    delete_register,
    get_all_registers,
    log_audit,
    update_register,
)
from ui.dialogs import confirm_delete
from ui.icon_manager import IconManager
from ui.notifications import friendly_error
from ui.theme import build_modern_widget_stylesheet, THEME_DARK, THEME_LIGHT, get_theme_mode


class RegisterManagementWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.selected_register_id: int | None = None
        self.create_ui()
        self.load_registers()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = IconManager.label("Register Management", "registers", "titleLabel", icon_size=20)
        
        subtitle_label = QLabel("Manage POS registers and terminals")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Content split
        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        
        # Left panel - Register form
        form_panel = self.create_form_panel()
        
        # Right panel - Register list
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
        
        section_label = IconManager.label("Register Details", "registers", "sectionLabel")
        layout.addWidget(section_label)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Name
        name_label = QLabel("Register Name")
        name_label.setObjectName("formLabel")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Main Register")
        
        form_layout.addWidget(name_label)
        form_layout.addWidget(self.name_input)
        
        # Location
        location_label = QLabel("Location")
        location_label.setObjectName("formLabel")
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("e.g., Store Front")
        
        form_layout.addWidget(location_label)
        form_layout.addWidget(self.location_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.add_button = QPushButton("Add Register")
        IconManager.apply_button(self.add_button, "add", IconManager.LIGHT)
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_register_action)
        
        self.update_button = QPushButton("Update Register")
        IconManager.apply_button(self.update_button, "edit", IconManager.LIGHT)
        self.update_button.setObjectName("secondaryButton")
        self.update_button.clicked.connect(self.update_register_action)
        
        self.delete_button = QPushButton("Delete Register")
        IconManager.apply_button(self.delete_button, "delete", IconManager.LIGHT)
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_register_action)
        
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
        
        section_label = IconManager.label("Registers", "registers", "sectionLabel")
        layout.addWidget(section_label)
        
        # Table
        self.registers_table = QTableWidget()
        self.registers_table.setColumnCount(4)
        self.registers_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Location", "Active"]
        )
        self.registers_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.registers_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.registers_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.registers_table.setAlternatingRowColors(True)
        self.registers_table.setShowGrid(False)
        self.registers_table.verticalHeader().setVisible(False)
        
        header = self.registers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.registers_table.itemSelectionChanged.connect(self.load_selected_register)
        
        layout.addWidget(self.registers_table, 1)
        
        return panel

    def load_registers(self) -> None:
        registers = get_all_registers()
        
        self.registers_table.setRowCount(len(registers))
        for row_index, register in enumerate(registers):
            values = [
                str(register["id"]),
                register["name"] or "",
                register["location"] or "",
                "Yes" if register["active"] else "No",
            ]
            
            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column_index == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, int(register["id"]))
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.registers_table.setItem(row_index, column_index, table_item)

    def reload_data(self) -> None:
        self.load_registers()

    def load_selected_register(self) -> None:
        selected_row = self.registers_table.currentRow()
        if selected_row < 0:
            return
        
        self.selected_register_id = int(
            self.registers_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        )
        
        registers = get_all_registers()
        register = next((r for r in registers if r["id"] == self.selected_register_id), None)
        
        if register:
            self.name_input.setText(register["name"])
            self.location_input.setText(register["location"])

    def add_register_action(self) -> None:
        name = self.name_input.text().strip()
        location = self.location_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter register name")
            return
        
        try:
            register_id = add_register(name, location)
            log_audit(self.current_user["id"], "CREATE_REGISTER", "registers", register_id, None, f"name: {name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", friendly_error(e))
            return
        
        self.clear_form()
        self.load_registers()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Register added successfully")

    def update_register_action(self) -> None:
        if self.selected_register_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a register to update")
            return
        
        name = self.name_input.text().strip()
        location = self.location_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter register name")
            return
        
        try:
            update_register(self.selected_register_id, name, location)
            log_audit(self.current_user["id"], "UPDATE_REGISTER", "registers", self.selected_register_id, None, f"name: {name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", friendly_error(e))
            return
        
        self.clear_form()
        self.load_registers()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Register updated successfully")

    def delete_register_action(self) -> None:
        if self.selected_register_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a register to delete")
            return
        
        if not confirm_delete(
            self,
            "Are you sure you want to delete this register?",
        ):
            return
        
        try:
            delete_register(self.selected_register_id)
            log_audit(self.current_user["id"], "DELETE_REGISTER", "registers", self.selected_register_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", friendly_error(e))
            return
        
        self.clear_form()
        self.load_registers()
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Register deleted successfully")

    def clear_form(self) -> None:
        self.selected_register_id = None
        self.registers_table.blockSignals(True)
        self.registers_table.clearSelection()
        self.registers_table.setCurrentCell(-1, -1)
        self.registers_table.blockSignals(False)
        
        self.name_input.clear()
        self.location_input.clear()
        self.name_input.setFocus()

    def apply_styles(self) -> None:
        mode = get_theme_mode()
        if mode == THEME_DARK:
            styles = """
            QWidget {
                background: #0F172A;
                color: #E5E7EB;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            #titleLabel {
                color: #F3F4F6;
                font-size: 26px;
                font-weight: 700;
            }

            #subtitleLabel {
                color: #D1D5DB;
                font-size: 13px;
            }

            #sectionLabel {
                color: #E5E7EB;
                font-size: 15px;
                font-weight: 700;
            }

            #panel {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 10px;
            }

            #formLabel {
                color: #D1D5DB;
                font-size: 12px;
                font-weight: 600;
            }

            QLineEdit {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 12px;
                color: #E5E7EB;
            }

            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 12px 14px;
            }

            #primaryButton {
                background: #3B82F6;
            }

            #secondaryButton {
                background: #059669;
            }

            #dangerButton {
                background: #EF4444;
            }
            
            #neutralButton {
                background: #475569;
            }

            QPushButton:pressed {
                padding-top: 13px;
                padding-bottom: 11px;
            }

            QTableWidget {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 8px;
                alternate-background-color: #0F172A;
                gridline-color: transparent;
                color: #E5E7EB;
            }

            QHeaderView::section {
                background: #1E293B;
                border: none;
                border-bottom: 1px solid #334155;
                color: #E5E7EB;
                font-weight: 700;
                padding: 10px;
            }

            QTableWidget::item {
                border-bottom: 1px solid #1E293B;
                padding: 8px;
            }
            """
        else:
            styles = """
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

            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 10px 12px;
            }

            QLineEdit:focus {
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
            """
        self.setStyleSheet(styles + build_modern_widget_stylesheet())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_register_management(current_user: dict) -> RegisterManagementWindow:
    window = RegisterManagementWindow(current_user)
    return window
