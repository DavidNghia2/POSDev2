from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from login import get_setting, log_audit, set_setting
from ui.icon_manager import IconManager


class SettingsWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.create_ui()
        self.load_settings()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        
        title_label = IconManager.label("Settings", "settings", "titleLabel", icon_size=20)
        
        subtitle_label = QLabel("System configuration")
        subtitle_label.setObjectName("subtitleLabel")
        
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Settings content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        
        # Left panel - Store Info
        left_panel = self.create_store_panel()
        
        # Right panel - Other Settings
        right_panel = self.create_other_settings_panel()
        
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        
        layout.addLayout(content_layout, 1)

    def create_store_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)
        
        section_label = IconManager.label("Store Information", "store", "sectionLabel")
        layout.addWidget(section_label)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Store name
        name_label = QLabel("Store Name")
        name_label.setObjectName("formLabel")
        self.store_name_input = QLineEdit()
        self.store_name_input.setPlaceholderText("Enter store name")
        
        form_layout.addWidget(name_label)
        form_layout.addWidget(self.store_name_input)
        
        # Store address
        address_label = QLabel("Address")
        address_label.setObjectName("formLabel")
        self.store_address_input = QLineEdit()
        self.store_address_input.setPlaceholderText("Enter store address")
        
        form_layout.addWidget(address_label)
        form_layout.addWidget(self.store_address_input)
        
        # Store phone
        phone_label = QLabel("Phone")
        phone_label.setObjectName("formLabel")
        self.store_phone_input = QLineEdit()
        self.store_phone_input.setPlaceholderText("Enter phone number")
        
        form_layout.addWidget(phone_label)
        form_layout.addWidget(self.store_phone_input)
        
        # Store email
        email_label = QLabel("Email")
        email_label.setObjectName("formLabel")
        self.store_email_input = QLineEdit()
        self.store_email_input.setPlaceholderText("Enter email")
        
        form_layout.addWidget(email_label)
        form_layout.addWidget(self.store_email_input)
        
        layout.addLayout(form_layout)
        
        # Save button
        self.save_store_button = QPushButton("Save Store Info")
        IconManager.apply_button(self.save_store_button, "save", IconManager.LIGHT)
        self.save_store_button.setObjectName("primaryButton")
        self.save_store_button.clicked.connect(self.save_store_settings)
        
        layout.addWidget(self.save_store_button)
        layout.addStretch()
        
        return panel

    def create_other_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)
        
        section_label = IconManager.label("Other Settings", "settings", "sectionLabel")
        layout.addWidget(section_label)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Tax settings
        tax_label = QLabel("Tax Rate (%)")
        tax_label.setObjectName("formLabel")
        self.tax_rate_input = QLineEdit()
        self.tax_rate_input.setPlaceholderText("e.g., 10")
        
        form_layout.addWidget(tax_label)
        form_layout.addWidget(self.tax_rate_input)
        
        # Currency
        currency_label = QLabel("Currency Symbol")
        currency_label.setObjectName("formLabel")
        self.currency_input = QLineEdit()
        self.currency_input.setPlaceholderText("e.g., $")
        
        form_layout.addWidget(currency_label)
        form_layout.addWidget(self.currency_input)
        
        # Receipt header
        receipt_header_label = QLabel("Receipt Header")
        receipt_header_label.setObjectName("formLabel")
        self.receipt_header_input = QLineEdit()
        self.receipt_header_input.setPlaceholderText("Text on receipt top")
        
        form_layout.addWidget(receipt_header_label)
        form_layout.addWidget(self.receipt_header_input)
        
        # Receipt footer
        receipt_footer_label = QLabel("Receipt Footer")
        receipt_footer_label.setObjectName("formLabel")
        self.receipt_footer_input = QLineEdit()
        self.receipt_footer_input.setPlaceholderText("Text on receipt bottom")
        
        form_layout.addWidget(receipt_footer_label)
        form_layout.addWidget(self.receipt_footer_input)
        
        layout.addLayout(form_layout)
        
        # Checkboxes
        checkbox_layout = QVBoxLayout()
        checkbox_layout.setSpacing(10)
        
        self.print_receipt_checkbox = QCheckBox("Auto-print receipts")
        self.print_receipt_checkbox.setChecked(True)
        
        self.sound_effects_checkbox = QCheckBox("Enable sound effects")
        self.sound_effects_checkbox.setChecked(True)
        
        self.offline_mode_checkbox = QCheckBox("Enable offline mode")
        self.offline_mode_checkbox.setChecked(True)
        
        checkbox_layout.addWidget(self.print_receipt_checkbox)
        checkbox_layout.addWidget(self.sound_effects_checkbox)
        checkbox_layout.addWidget(self.offline_mode_checkbox)
        
        layout.addLayout(checkbox_layout)
        
        # Save button
        self.save_other_button = QPushButton("Save Other Settings")
        IconManager.apply_button(self.save_other_button, "save", IconManager.LIGHT)
        self.save_other_button.setObjectName("secondaryButton")
        self.save_other_button.clicked.connect(self.save_other_settings)
        
        layout.addWidget(self.save_other_button)
        layout.addStretch()
        
        return panel

    def load_settings(self) -> None:
        # Store info
        self.store_name_input.setText(get_setting("store_name") or "")
        self.store_address_input.setText(get_setting("store_address") or "")
        self.store_phone_input.setText(get_setting("store_phone") or "")
        self.store_email_input.setText(get_setting("store_email") or "")
        
        # Other settings
        self.tax_rate_input.setText(get_setting("tax_rate") or "10")
        self.currency_input.setText(get_setting("currency") or "$")
        self.receipt_header_input.setText(get_setting("receipt_header") or "Thank You!")
        self.receipt_footer_input.setText(get_setting("receipt_footer") or "Please come again")
        
        self.print_receipt_checkbox.setChecked(get_setting("auto_print") != "false")
        self.sound_effects_checkbox.setChecked(get_setting("sound_effects") != "false")
        self.offline_mode_checkbox.setChecked(get_setting("offline_mode") != "false")

    def reload_data(self) -> None:
        self.load_settings()

    def save_store_settings(self) -> None:
        set_setting("store_name", self.store_name_input.text().strip())
        set_setting("store_address", self.store_address_input.text().strip())
        set_setting("store_phone", self.store_phone_input.text().strip())
        set_setting("store_email", self.store_email_input.text().strip())
        
        log_audit(self.current_user["id"], "UPDATE_SETTINGS", "settings", None, None, "store_info")
        
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Store settings saved successfully")

    def save_other_settings(self) -> None:
        set_setting("tax_rate", self.tax_rate_input.text().strip())
        set_setting("currency", self.currency_input.text().strip())
        set_setting("receipt_header", self.receipt_header_input.text().strip())
        set_setting("receipt_footer", self.receipt_footer_input.text().strip())
        
        set_setting("auto_print", "true" if self.print_receipt_checkbox.isChecked() else "false")
        set_setting("sound_effects", "true" if self.sound_effects_checkbox.isChecked() else "false")
        set_setting("offline_mode", "true" if self.offline_mode_checkbox.isChecked() else "false")
        
        log_audit(self.current_user["id"], "UPDATE_SETTINGS", "settings", None, None, "other_settings")
        
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Settings saved successfully")

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
                min-width: 380px;
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

            QPushButton:pressed {
                padding-top: 13px;
                padding-bottom: 11px;
            }

            QCheckBox {
                background: transparent;
                spacing: 8px;
                font-weight: 500;
            }
            """
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_settings(current_user: dict) -> SettingsWindow:
    window = SettingsWindow(current_user)
    return window
