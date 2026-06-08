from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from login import get_setting, log_audit, set_setting
from ui.currency import CURRENCY_OPTIONS, DEFAULT_CURRENCY_CODE, normalize_currency_code
from ui.icon_manager import IconManager
from ui.notifications import friendly_error
from ui.theme import build_modern_widget_stylesheet, THEME_DARK, THEME_LIGHT, get_theme_mode
from ui.qr_display import qr_focus_pixmap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"
PAYMENT_QR_SETTING_KEY = "bank_qr_image_path"
QR_PREVIEW_SIZE = 260


class CurrencySelect(QComboBox):
    def __init__(
        self,
        options: tuple[tuple[str, str], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(12)
        self.setMinimumContentsLength(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view().setObjectName("settingsSelectList")
        self.lineEdit().setPlaceholderText("Search currency")

        for label, code in options:
            self.addItem(label, code)

        completer = QCompleter([label for label, _code in options], self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.popup().setObjectName("settingsSelectList")
        self.setCompleter(completer)

    def currentData(self, role: int = int(Qt.ItemDataRole.UserRole)) -> str:
        if role != int(Qt.ItemDataRole.UserRole):
            return super().currentData(role) or ""
        current_text = self.currentText().strip()
        for index in range(self.count()):
            if self.itemText(index) == current_text:
                return self.itemData(index, Qt.ItemDataRole.UserRole)
        return super().currentData(Qt.ItemDataRole.UserRole) or DEFAULT_CURRENCY_CODE

    def findData(self, value: str) -> int:
        code = normalize_currency_code(value)
        for index in range(self.count()):
            if self.itemData(index) == code:
                return index
        return -1


class SettingsWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, current_user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.selected_qr_source_path: Path | None = None
        self.saved_qr_image_path = ""
        self.create_ui()
        self.load_settings()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

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

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.addTab(self.create_store_tab(), "Store Information")
        self.tabs.addTab(self.create_receipt_tab(), "Receipt Settings")
        self.tabs.addTab(self.create_payment_tab(), "Payment Settings")

        layout.addWidget(self.tabs, 1)

    def create_tab_panel(self, title: str, icon_key: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        section_label = IconManager.label(title, icon_key, "sectionLabel")
        layout.addWidget(section_label)

        panel.content_layout = layout  # type: ignore[attr-defined]
        return panel

    def add_input(
        self,
        layout: QVBoxLayout,
        label_text: str,
        placeholder: str = "",
    ) -> QLineEdit:
        label = QLabel(label_text)
        label.setObjectName("formLabel")

        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)

        layout.addWidget(label)
        layout.addWidget(input_field)
        return input_field

    def add_text_area(
        self,
        layout: QVBoxLayout,
        label_text: str,
        placeholder: str = "",
    ) -> QTextEdit:
        label = QLabel(label_text)
        label.setObjectName("formLabel")

        text_area = QTextEdit()
        text_area.setPlaceholderText(placeholder)
        text_area.setFixedHeight(76)

        layout.addWidget(label)
        layout.addWidget(text_area)
        return text_area

    def add_select(
        self,
        layout: QVBoxLayout,
        label_text: str,
        options: tuple[tuple[str, str], ...],
    ) -> CurrencySelect:
        label = QLabel(label_text)
        label.setObjectName("formLabel")

        combo = CurrencySelect(options)
        combo.setObjectName("settingsSelect")

        layout.addWidget(label)
        layout.addWidget(combo)
        return combo

    def create_store_tab(self) -> QFrame:
        panel = self.create_tab_panel("Store Information", "store")
        layout = panel.content_layout  # type: ignore[attr-defined]

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.store_name_input = self.add_input(form_layout, "Store Name", "Enter store name")
        self.store_address_input = self.add_input(form_layout, "Address", "Enter store address")
        self.store_phone_input = self.add_input(form_layout, "Phone", "Enter phone number")
        self.store_email_input = self.add_input(form_layout, "Email", "Enter email")

        layout.addLayout(form_layout)
        layout.addStretch(1)

        self.save_store_button = QPushButton("Save")
        IconManager.apply_button(self.save_store_button, "save", IconManager.LIGHT)
        self.save_store_button.setObjectName("primaryButton")
        self.save_store_button.clicked.connect(self.save_store_settings)
        layout.addWidget(self.save_store_button, 0, Qt.AlignmentFlag.AlignLeft)

        return panel

    def create_receipt_tab(self) -> QFrame:
        panel = self.create_tab_panel("Receipt Settings", "receipt")
        layout = panel.content_layout  # type: ignore[attr-defined]

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.currency_combo = self.add_select(form_layout, "Currency Symbol", CURRENCY_OPTIONS)
        self.receipt_header_input = self.add_text_area(form_layout, "Receipt Header", "Text on receipt top")
        self.receipt_footer_input = self.add_text_area(form_layout, "Receipt Footer", "Text on receipt bottom")

        layout.addLayout(form_layout)

        layout.addStretch(1)

        self.save_receipt_button = QPushButton("Save")
        IconManager.apply_button(self.save_receipt_button, "save", IconManager.LIGHT)
        self.save_receipt_button.setObjectName("primaryButton")
        self.save_receipt_button.clicked.connect(self.save_receipt_settings)
        layout.addWidget(self.save_receipt_button, 0, Qt.AlignmentFlag.AlignLeft)

        return panel

    def create_payment_tab(self) -> QFrame:
        panel = self.create_tab_panel("Payment Settings", "payment")
        layout = panel.content_layout  # type: ignore[attr-defined]

        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        form_panel = QFrame()
        form_panel.setObjectName("settingsFormPanel")
        form_panel_layout = QVBoxLayout(form_panel)
        form_panel_layout.setContentsMargins(0, 0, 0, 0)
        form_panel_layout.setSpacing(14)

        self.enable_bank_transfer_checkbox = QCheckBox("Enable Bank Transfer")
        self.enable_bank_transfer_checkbox.setObjectName("settingsToggle")
        form_panel_layout.addWidget(self.enable_bank_transfer_checkbox)

        self.upload_qr_button = QPushButton("Upload QR Image")
        IconManager.apply_button(self.upload_qr_button, "upload", IconManager.LIGHT)
        self.upload_qr_button.setObjectName("secondaryButton")
        self.upload_qr_button.clicked.connect(self.upload_qr_image)
        form_panel_layout.addWidget(self.upload_qr_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.qr_path_label = QLabel("No QR image selected")
        self.qr_path_label.setObjectName("helperText")
        self.qr_path_label.setWordWrap(True)
        self.qr_path_label.setMaximumWidth(520)
        form_panel_layout.addWidget(self.qr_path_label)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.bank_name_input = self.add_input(form_layout, "Bank Name", "Enter bank name")
        self.account_name_input = self.add_input(form_layout, "Account Name", "Enter account name")
        self.account_number_input = self.add_input(form_layout, "Account Number", "Enter account number")

        form_panel_layout.addLayout(form_layout)
        form_panel_layout.addStretch(1)

        self.save_payment_button = QPushButton("Save")
        IconManager.apply_button(self.save_payment_button, "save", IconManager.LIGHT)
        self.save_payment_button.setObjectName("primaryButton")
        self.save_payment_button.clicked.connect(self.save_payment_settings)
        form_panel_layout.addWidget(self.save_payment_button, 0, Qt.AlignmentFlag.AlignLeft)

        preview_panel = QFrame()
        preview_panel.setObjectName("qrPreviewCard")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(22, 22, 22, 22)
        preview_layout.setSpacing(12)

        preview_title = QLabel("QR Preview")
        preview_title.setObjectName("previewTitle")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_hint = QLabel("Cashier payment screen will show only this focused QR area.")
        preview_hint.setObjectName("helperText")
        preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_hint.setWordWrap(True)

        self.qr_preview_label = QLabel("QR Preview")
        self.qr_preview_label.setObjectName("qrPreview")
        self.qr_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_preview_label.setFixedSize(QR_PREVIEW_SIZE, QR_PREVIEW_SIZE)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_hint)
        preview_layout.addStretch(1)
        preview_layout.addWidget(self.qr_preview_label, 0, Qt.AlignmentFlag.AlignCenter)
        preview_layout.addStretch(1)

        content_layout.addWidget(form_panel, 3)
        content_layout.addWidget(preview_panel, 2)
        layout.addLayout(content_layout, 1)

        return panel

    def load_settings(self) -> None:
        self.store_name_input.setText(get_setting("store_name") or "")
        self.store_address_input.setText(get_setting("store_address") or "")
        self.store_phone_input.setText(get_setting("store_phone") or "")
        self.store_email_input.setText(get_setting("store_email") or "")

        currency_code = normalize_currency_code(
            get_setting("currency_symbol") or get_setting("currency")
        )
        currency_index = self.currency_combo.findData(currency_code)
        self.currency_combo.setCurrentIndex(max(currency_index, 0))
        self.receipt_header_input.setPlainText(get_setting("receipt_header") or "Thank You!")
        self.receipt_footer_input.setPlainText(get_setting("receipt_footer") or "Please come again")

        self.enable_bank_transfer_checkbox.setChecked(get_setting("enable_bank_transfer") != "false")
        self.saved_qr_image_path = get_setting(PAYMENT_QR_SETTING_KEY) or ""
        self.selected_qr_source_path = None
        self.update_qr_preview(self.resolve_project_path(self.saved_qr_image_path))
        self.bank_name_input.setText(get_setting("bank_name") or "")
        self.account_name_input.setText(get_setting("account_name") or get_setting("bank_account_name") or "")
        self.account_number_input.setText(get_setting("account_number") or get_setting("bank_account_number") or "")

    def reload_data(self) -> None:
        self.load_settings()

    def resolve_project_path(self, path_value: str) -> Path | None:
        if not path_value:
            return None

        path = Path(path_value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def update_qr_preview(self, image_path: Path | None) -> None:
        if image_path is None or not image_path.exists():
            self.qr_preview_label.clear()
            self.qr_preview_label.setText("QR Preview")
            self.qr_path_label.setText("No QR image selected")
            return

        pixmap = qr_focus_pixmap(image_path, QR_PREVIEW_SIZE)
        if pixmap.isNull():
            self.qr_preview_label.clear()
            self.qr_preview_label.setText("Unable to preview this image")
            self.qr_path_label.setText(str(image_path))
            return

        self.qr_preview_label.setText("")
        self.qr_preview_label.setPixmap(pixmap)
        try:
            display_path = image_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = Path(image_path.name)
        self.qr_path_label.setText(f"Selected image: {display_path}")

    def upload_qr_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload QR Image",
            str(PROJECT_ROOT),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if not file_path:
            return

        self.selected_qr_source_path = Path(file_path)
        self.update_qr_preview(self.selected_qr_source_path)

    def persist_qr_image(self, source_path: Path) -> str:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = source_path.suffix.lower() or ".png"
        destination = ASSETS_DIR / f"payment_qr{suffix}"

        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)

        return destination.relative_to(PROJECT_ROOT).as_posix()

    def save_store_settings(self) -> None:
        set_setting("store_name", self.store_name_input.text().strip())
        set_setting("store_address", self.store_address_input.text().strip())
        set_setting("store_phone", self.store_phone_input.text().strip())
        set_setting("store_email", self.store_email_input.text().strip())

        log_audit(self.current_user["id"], "UPDATE_SETTINGS", "settings", None, None, "store_information")

        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Store information saved successfully")

    def save_receipt_settings(self) -> None:
        currency_code = self.currency_combo.currentData() or DEFAULT_CURRENCY_CODE
        set_setting("currency_symbol", currency_code)
        set_setting("currency", currency_code)
        set_setting("receipt_header", self.receipt_header_input.toPlainText().strip())
        set_setting("receipt_footer", self.receipt_footer_input.toPlainText().strip())

        log_audit(self.current_user["id"], "UPDATE_SETTINGS", "settings", None, None, "receipt_settings")

        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Receipt settings saved successfully")

    def save_payment_settings(self) -> None:
        if self.selected_qr_source_path is not None:
            try:
                self.saved_qr_image_path = self.persist_qr_image(self.selected_qr_source_path)
            except OSError as error:
                QMessageBox.warning(self, "QR Image Error", friendly_error(error))
                return

        set_setting(
            "enable_bank_transfer",
            "true" if self.enable_bank_transfer_checkbox.isChecked() else "false",
        )
        set_setting(PAYMENT_QR_SETTING_KEY, self.saved_qr_image_path)
        set_setting("bank_name", self.bank_name_input.text().strip())
        account_name = self.account_name_input.text().strip()
        account_number = self.account_number_input.text().strip()
        set_setting("account_name", account_name)
        set_setting("account_number", account_number)
        set_setting("bank_account_name", account_name)
        set_setting("bank_account_number", account_number)

        log_audit(self.current_user["id"], "UPDATE_SETTINGS", "settings", None, None, "payment_settings")

        self.selected_qr_source_path = None
        self.update_qr_preview(self.resolve_project_path(self.saved_qr_image_path))
        self.data_changed.emit()
        QMessageBox.information(self, "Success", "Payment settings saved successfully")

    def apply_styles(self) -> None:
        mode = get_theme_mode()
        if mode == THEME_DARK:
            styles = """
            QWidget {
                background: #101820;
                color: #E6EDF3;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QLabel {
                background: transparent;
            }

            #titleLabel {
                color: #F5F8FA;
                font-size: 26px;
                font-weight: 700;
            }

            #subtitleLabel {
                color: #C8D3DF;
                font-size: 13px;
            }

            #sectionLabel {
                color: #E6EDF3;
                font-size: 16px;
                font-weight: 700;
            }

            #settingsTabs {
                background: transparent;
            }

            QTabWidget::pane {
                border: none;
                margin-top: 12px;
            }

            QTabBar::tab {
                background: #1F2A37;
                color: #A7B3C2;
                border: 1px solid #314154;
                border-radius: 9px;
                padding: 9px 15px;
                margin-right: 7px;
                font-weight: 700;
            }

            QTabBar::tab:selected {
                background: #60A5FA;
                color: #FFFFFF;
                border-color: #60A5FA;
            }

            QTabBar::tab:hover:!selected {
                background: #46586A;
                color: #E6EDF3;
            }

            #panel {
                background: #17212B;
                border: 1px solid #314154;
                border-radius: 12px;
            }

            #settingsFormPanel {
                background: transparent;
                border: none;
            }

            #qrPreviewCard {
                background: #1F2A37;
                border: 1px solid #314154;
                border-radius: 14px;
                min-width: 330px;
            }

            #previewTitle {
                color: #E6EDF3;
                font-size: 15px;
                font-weight: 800;
            }

            #formLabel {
                color: #C8D3DF;
                font-size: 12px;
                font-weight: 700;
            }

            #helperText {
                background: transparent;
                color: #C8D3DF;
                font-size: 12px;
            }

            QLineEdit {
                background: #1F2A37;
                border: 1px solid #314154;
                border-radius: 8px;
                padding: 10px 12px;
                min-height: 18px;
                color: #E6EDF3;
            }

            QLineEdit:focus {
                border: 1px solid #60A5FA;
            }

            #settingsSelect {
                background: #1F2A37;
                border: 1px solid #314154;
                border-radius: 8px;
                color: #E6EDF3;
                font-weight: 600;
                min-height: 40px;
                min-width: 320px;
                padding: 0 38px 0 12px;
            }

            #settingsSelect:hover {
                background: #101820;
                border: 1px solid #46586A;
            }

            #settingsSelect:focus,
            #settingsSelect:on {
                border: 1px solid #60A5FA;
            }

            #settingsSelect::drop-down {
                border: none;
                width: 34px;
            }

            #settingsSelect::down-arrow {
                image: url(assets/ui_chevron_down.svg);
                width: 18px;
                height: 18px;
                margin-right: 11px;
            }

            #settingsSelect QLineEdit {
                background: transparent;
                border: none;
                color: #E6EDF3;
                font-weight: 600;
                padding: 0;
                min-height: 36px;
            }

            #settingsSelectList {
                background: #17212B;
                border: 1px solid #314154;
                border-radius: 8px;
                color: #E6EDF3;
                outline: none;
                padding: 6px;
            }

            #settingsSelectList::item {
                min-height: 30px;
                padding: 7px 10px;
                border-radius: 6px;
            }

            #settingsSelectList::item:hover,
            #settingsSelectList::item:selected {
                background: #1E3A5F;
                color: #E6EDF3;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 6px 12px;
                min-height: 32px;
                min-width: 82px;
            }

            #primaryButton {
                background: #60A5FA;
            }

            #secondaryButton {
                background: #059669;
            }

            QPushButton:pressed {
                padding-top: 7px;
                padding-bottom: 5px;
            }

            QCheckBox {
                background: transparent;
                spacing: 7px;
                font-weight: 600;
                color: #E6EDF3;
            }

            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid #46586A;
                border-radius: 5px;
                background: #1F2A37;
            }

            QCheckBox::indicator:checked {
                background: #60A5FA;
                border-color: #60A5FA;
            }

            #qrPreview {
                background: #101820;
                border: 1px dashed #46586A;
                border-radius: 12px;
                color: #A7B3C2;
                font-weight: 700;
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

            QLabel {
                background: transparent;
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
                font-size: 16px;
                font-weight: 700;
            }

            #settingsTabs {
                background: transparent;
            }

            QTabWidget::pane {
                border: none;
                margin-top: 12px;
            }

            QTabBar::tab {
                background: #FFFFFF;
                color: #526170;
                border: 1px solid #D8E0E8;
                border-radius: 9px;
                padding: 9px 15px;
                margin-right: 7px;
                font-weight: 700;
            }

            QTabBar::tab:selected {
                background: #2563EB;
                color: #FFFFFF;
                border-color: #2563EB;
            }

            QTabBar::tab:hover:!selected {
                background: #F8FAFC;
                color: #17212B;
            }

            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 12px;
            }

            #settingsFormPanel {
                background: transparent;
                border: none;
            }

            #qrPreviewCard {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 14px;
                min-width: 330px;
            }

            #previewTitle {
                color: #25313D;
                font-size: 15px;
                font-weight: 800;
            }

            #formLabel {
                color: #64707D;
                font-size: 12px;
                font-weight: 700;
            }

            #helperText {
                background: transparent;
                color: #64707D;
                font-size: 12px;
            }

            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 10px 12px;
                min-height: 18px;
            }

            QLineEdit:focus {
                border: 1px solid #2563EB;
            }

            #settingsSelect {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                color: #17212B;
                font-weight: 600;
                min-height: 40px;
                min-width: 320px;
                padding: 0 38px 0 12px;
            }

            #settingsSelect:hover {
                background: #F8FAFC;
                border: 1px solid #B8C6D5;
            }

            #settingsSelect:focus,
            #settingsSelect:on {
                border: 1px solid #2563EB;
            }

            #settingsSelect::drop-down {
                border: none;
                width: 34px;
            }

            #settingsSelect::down-arrow {
                image: url(assets/ui_chevron_down.svg);
                width: 18px;
                height: 18px;
                margin-right: 11px;
            }

            #settingsSelect QLineEdit {
                background: transparent;
                border: none;
                color: #17212B;
                font-weight: 600;
                padding: 0;
                min-height: 36px;
            }

            #settingsSelectList {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 8px;
                color: #17212B;
                outline: none;
                padding: 6px;
            }

            #settingsSelectList::item {
                min-height: 30px;
                padding: 7px 10px;
                border-radius: 6px;
            }

            #settingsSelectList::item:hover,
            #settingsSelectList::item:selected {
                background: #DBEAFE;
                color: #17212B;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 6px 12px;
                min-height: 32px;
                min-width: 82px;
            }

            #primaryButton {
                background: #2563EB;
            }

            #secondaryButton {
                background: #0F766E;
            }

            QPushButton:pressed {
                padding-top: 7px;
                padding-bottom: 5px;
            }

            QCheckBox {
                background: transparent;
                spacing: 7px;
                font-weight: 600;
                color: #25313D;
            }

            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid #A7B3C2;
                border-radius: 5px;
                background: #FFFFFF;
            }

            QCheckBox::indicator:checked {
                background: #2563EB;
                border-color: #2563EB;
            }

            #qrPreview {
                background: #FFFFFF;
                border: 1px dashed #A7B3C2;
                border-radius: 12px;
                color: #64707D;
                font-weight: 700;
            }
            """
        self.setStyleSheet(styles + build_modern_widget_stylesheet())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.apply_styles()


def create_settings(current_user: dict) -> SettingsWindow:
    window = SettingsWindow(current_user)
    return window
