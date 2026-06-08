"""Shared modern UI theme snippets for the POS desktop app."""

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QComboBox, QFrame

THEME_LIGHT = "light"
THEME_DARK = "dark"
_CURRENT_THEME_MODE = THEME_LIGHT


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
CHECK_ICON_URL = (ASSETS_DIR / "ui_check.svg").as_posix()
RADIO_DOT_ICON_URL = (ASSETS_DIR / "ui_radio_dot.svg").as_posix()


def set_theme_mode(mode: str) -> str:
    global _CURRENT_THEME_MODE
    normalized = (mode or "").strip().lower()
    _CURRENT_THEME_MODE = THEME_DARK if normalized == THEME_DARK else THEME_LIGHT
    return _CURRENT_THEME_MODE


def get_theme_mode() -> str:
    return _CURRENT_THEME_MODE


def is_dark_mode() -> bool:
    return _CURRENT_THEME_MODE == THEME_DARK


def _popup_colors(mode: str | None = None) -> dict[str, str]:
    active = mode or get_theme_mode()
    if active == THEME_DARK:
        return {
            "bg": "#17212B",
            "border": "#314154",
            "item_text": "#E6EDF3",
            "hover_bg": "#2563EB",
            "hover_text": "#FFFFFF",
        }
    return {
        "bg": "#FFFFFF",
        "border": "#C8D3DF",
        "item_text": "#101820",
        "hover_bg": "#2563EB",
        "hover_text": "#FFFFFF",
    }


def build_combo_popup_stylesheet(mode: str | None = None) -> str:
    c = _popup_colors(mode)
    return f"""
QListView,
QAbstractItemView {{
    background: {c["bg"]};
    background-color: {c["bg"]};
    border: 1px solid {c["border"]};
    border-radius: 0;
    margin: 0;
    outline: 0;
    padding: 0;
    selection-background-color: {c["hover_bg"]};
    selection-color: {c["hover_text"]};
}}

QListView::item,
QAbstractItemView::item {{
    background: {c["bg"]};
    color: {c["item_text"]};
    min-height: 28px;
    padding: 6px 10px;
}}

QListView::item:hover,
QListView::item:selected,
QAbstractItemView::item:hover,
QAbstractItemView::item:selected {{
    background: {c["hover_bg"]};
    color: {c["hover_text"]};
}}
"""


def apply_combobox_popup_fix(combo: QComboBox) -> None:
    """Keep combo popups from showing native black corners on Windows/Fusion."""
    view = combo.view()
    if view is None:
        return

    popup = _popup_colors()
    popup_bg = popup["bg"]

    container = view.parentWidget()
    if container is not None:
        container_palette = container.palette()
        container_palette.setColor(QPalette.ColorRole.Base, QColor(popup_bg))
        container_palette.setColor(QPalette.ColorRole.Window, QColor(popup_bg))
        container.setPalette(container_palette)
        container.setAutoFillBackground(True)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        container.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        container.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        container.setStyleSheet(
            f"""
            QFrame {{
                background: {popup_bg};
                background-color: {popup_bg};
                border: none;
                border-radius: 0;
                margin: 0;
                padding: 0;
            }}
            """
        )

    palette = view.palette()
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Window,
        QPalette.ColorRole.AlternateBase,
    ):
        palette.setColor(role, QColor(popup_bg))
    view.setPalette(palette)
    view.viewport().setPalette(palette)

    view.setAutoFillBackground(True)
    view.viewport().setAutoFillBackground(True)
    view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    view.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    view.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
    view.viewport().setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
    view.setFrameShape(QFrame.Shape.NoFrame)
    view.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
    view.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    view.setStyleSheet(build_combo_popup_stylesheet())
    combo.setProperty("_retail_pos_combo_popup_fixed", True)


class ComboBoxPopupFixer(QObject):
    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QComboBox) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            QTimer.singleShot(0, lambda combo=watched: apply_combobox_popup_fix(combo))
        elif isinstance(watched, QFrame) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
        }:
            parent = watched.parent()
            if isinstance(parent, QComboBox):
                QTimer.singleShot(0, lambda combo=parent: apply_combobox_popup_fix(combo))
        return False


def install_combobox_popup_fix(app: QApplication) -> None:
    if getattr(app, "_retail_pos_combo_popup_fixer", None) is None:
        fixer = ComboBoxPopupFixer(app)
        app.installEventFilter(fixer)
        app._retail_pos_combo_popup_fixer = fixer

    for widget in app.allWidgets():
        if isinstance(widget, QComboBox):
            apply_combobox_popup_fix(widget)


def build_modern_widget_stylesheet(mode: str | None = None) -> str:
    active = mode or get_theme_mode()
    if active == THEME_DARK:
        return f"""
QWidget {{
    color: #E6EDF3;
    font-family: "Segoe UI";
    font-size: 13px;
    background: #101820;
}}

QDialog, QFrame, QScrollArea, QListView, QAbstractItemView, QMenu, QMenuBar {{
    background: #17212B;
}}

QLabel {{
    background: transparent;
}}

QFrame#panel,
QFrame#cardPanel,
QFrame#checkoutPanel,
QFrame#dialogPanel,
QFrame#paymentDialogPanel,
QFrame#qrPreviewCard {{
    border-radius: 14px;
}}

QPushButton {{
    background: #1F2A37;
    color: #E6EDF3;
    border: none;
    border-radius: 8px;
    font-weight: 750;
    min-height: 30px;
    min-width: 74px;
    padding: 5px 11px;
}}

QPushButton:hover {{
    background: #17212B;
}}

QPushButton:pressed {{
    padding-top: 6px;
    padding-bottom: 4px;
    background: #223041;
}}

QPushButton:disabled {{
    background: #314154;
    color: #A7B3C2;
}}

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit {{
    background: #17212B;
    border: 1px solid #314154;
    border-radius: 8px;
    color: #E6EDF3;
    min-height: 18px;
    padding: 7px 10px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}}

QLineEdit:hover,
QComboBox:hover,
QDateEdit:hover,
QTextEdit:hover {{
    border-color: #46586A;
}}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus {{
    border: 1px solid #2563EB;
}}

QComboBox {{
    combobox-popup: 0;
    padding-right: 30px;
}}

QComboBox::drop-down,
QDateEdit::drop-down {{
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
}}

QComboBox QAbstractItemView {{
    background: #17212B;
    border: 1px solid #314154;
    border-radius: 0;
    outline: 0;
    padding: 0;
    margin: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}}

QComboBox QAbstractItemView::item {{
    background: #17212B;
    color: #E6EDF3;
    min-height: 28px;
    padding: 6px 10px;
}}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background: #2563EB;
    color: #FFFFFF;
}}

QCheckBox {{
    background: transparent;
    color: #E6EDF3;
    font-weight: 650;
    spacing: 7px;
}}

QCheckBox::indicator {{
    background: #17212B;
    border: 1px solid #708195;
    border-radius: 5px;
    height: 17px;
    width: 17px;
}}

QCheckBox::indicator:hover {{
    border-color: #2563EB;
}}

QCheckBox::indicator:checked {{
    background: #2563EB;
    border-color: #2563EB;
    image: url("{CHECK_ICON_URL}");
}}

QRadioButton {{
    background: #17212B;
    border: 1px solid #314154;
    border-radius: 10px;
    color: #E6EDF3;
    font-weight: 750;
    padding: 8px 11px;
    spacing: 7px;
}}

QRadioButton:hover {{
    background: #101820;
    border-color: #46586A;
}}

QRadioButton:checked {{
    background: #223041;
    border-color: #2563EB;
    color: #93C5FD;
}}

QRadioButton::indicator {{
    background: #17212B;
    border: 1px solid #708195;
    border-radius: 7px;
    height: 15px;
    width: 15px;
}}

QRadioButton::indicator:checked {{
    background: #17212B;
    border: 2px solid #2563EB;
    border-radius: 7px;
    image: url("{RADIO_DOT_ICON_URL}");
}}

#primaryButton,
#primaryDialogButton,
#dashboardActionButton[role="primary"],
#rowEditButton,
#smallButton {{
    background: #2563EB;
    color: #FFFFFF;
}}

#primaryButton:hover,
#primaryDialogButton:hover,
#dashboardActionButton[role="primary"]:hover,
#rowEditButton:hover,
#smallButton:hover {{
    background: #1D4ED8;
}}

#secondaryButton,
#dashboardActionButton[role="secondary"] {{
    background: #0F766E;
    color: #FFFFFF;
}}

#secondaryButton:hover,
#dashboardActionButton[role="secondary"]:hover {{
    background: #0D5F59;
}}

#dangerButton,
#rowDeleteButton {{
    background: #DC2626;
    color: #FFFFFF;
}}

#dangerButton:hover,
#rowDeleteButton:hover {{
    background: #B91C1C;
}}

#neutralButton,
#neutralDialogButton {{
    background: #314154;
    color: #E6EDF3;
}}

#neutralButton:hover,
#neutralDialogButton:hover {{
    background: #46586A;
}}

#primaryButton,
#secondaryButton,
#dangerButton,
#neutralButton,
#primaryDialogButton,
#neutralDialogButton,
#dashboardActionButton {{
    min-height: 32px;
    min-width: 82px;
    padding: 6px 12px;
}}

#primaryDialogButton,
#neutralDialogButton {{
    min-width: 96px;
    max-width: 150px;
}}

#rowEditButton,
#rowDeleteButton,
#smallButton {{
    min-height: 28px;
    min-width: 72px;
    padding: 4px 9px;
}}

KeypadButton {{
    min-height: 46px;
}}

ActionButton {{
    min-height: 42px;
    padding: 8px 12px;
}}

#payButton {{
    min-height: 46px;
    font-size: 14px;
}}

#splitButton,
#cancelButton {{
    min-height: 42px;
}}

QTableWidget {{
    alternate-background-color: #101820;
    background: #17212B;
    border: 1px solid #314154;
    border-radius: 12px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #274B7A;
    selection-color: #E6EDF3;
}}

QHeaderView::section {{
    background: #101820;
    border: none;
    border-bottom: 1px solid #314154;
    color: #C8D3DF;
    font-weight: 800;
    padding: 11px 10px;
}}

QTableWidget::item {{
    border-bottom: 1px solid #1F2A37;
    padding: 8px 10px;
}}

QTableWidget::item:selected {{
    background: #274B7A;
    color: #E6EDF3;
}}

QMessageBox {{
    background: #101820;
}}

QMessageBox QLabel {{
    background: transparent;
    color: #E6EDF3;
    font-size: 13px;
}}

QMessageBox QPushButton {{
    background: #2563EB;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 750;
    max-width: 110px;
    min-height: 32px;
    min-width: 76px;
    padding: 6px 12px;
}}

QMessageBox QPushButton:hover {{
    background: #1D4ED8;
}}

QScrollBar:vertical {{
    background: #101820;
    border: none;
    width: 12px;
}}

QScrollBar::handle:vertical {{
    background: #46586A;
    border-radius: 6px;
    min-height: 34px;
}}

QScrollBar::handle:vertical:hover {{
    background: #708195;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    border: none;
    height: 0;
}}

#titleLabel,
#subtitleLabel,
#sectionLabel,
#helperLabel,
#statusLabel,
#formLabel,
#paymentCount,
#paymentAmount,
#productQty,
#productSales,
#statTitle,
#statValue,
#noDataLabel {{
    color: #C8D3DF;
}}

#panel,
#statCard,
#detailPanel,
#dashboardCard,
#formPanel,
#paymentDialogPanel,
#checkoutPanel,
#dialogPanel,
#qrPreviewCard,
#cardPanel,
#dialogScroll,
#dialogBody,
#imagePreview,
#tableImage,
#barcodeScroll,
#barcodeRow,
#barcodeVariant,
#emptyBarcodeLabel,
#barcodeRules {{
    background: #17212B;
    border: 1px solid #314154;
}}

QTableView,
QTableWidget {{
    background: #17212B;
    border: 1px solid #314154;
    color: #E6EDF3;
}}

QTableView::item,
QTableWidget::item {{
    background: #17212B;
    color: #E6EDF3;
}}

QDateEdit,
QComboBox,
QLineEdit,
QTextEdit {{
    background: #17212B;
    border: 1px solid #314154;
    color: #E6EDF3;
}}

QComboBox QAbstractItemView::item {{
    background: #17212B;
    color: #E6EDF3;
}}

QHeaderView::section {{
    background: #17212B;
    border-color: #314154;
    color: #C8D3DF;
}}

QWidget#mainWindow,
QWidget#dashboardPage,
QWidget#pageContainer {{
    background: #101820;
}}
"""
    return """
QWidget {
    color: #101820;
    font-family: "Segoe UI";
    font-size: 13px;
}

QLabel {
    background: transparent;
}

QFrame#panel,
QFrame#cardPanel,
QFrame#checkoutPanel,
QFrame#dialogPanel,
QFrame#paymentDialogPanel,
QFrame#qrPreviewCard {
    border-radius: 14px;
}

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit {
    background: #FFFFFF;
    border: 1px solid #C8D3DF;
    border-radius: 8px;
    color: #101820;
    min-height: 18px;
    padding: 7px 10px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QLineEdit:hover,
QComboBox:hover,
QDateEdit:hover,
QTextEdit:hover {
    border-color: #A7B3C2;
}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus {
    border: 1px solid #2563EB;
}

QComboBox {
    combobox-popup: 0;
    padding-right: 30px;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
}

QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #C8D3DF;
    border-radius: 0;
    outline: 0;
    padding: 0;
    margin: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QComboBox QAbstractItemView::item {
    background: #FFFFFF;
    color: #101820;
    min-height: 28px;
    padding: 6px 10px;
}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {
    background: #2563EB;
    color: #FFFFFF;
}

QCheckBox {
    background: transparent;
    color: #101820;
    font-weight: 650;
    spacing: 7px;
}

QCheckBox::indicator {
    background: #FFFFFF;
    border: 1px solid #A7B3C2;
    border-radius: 5px;
    height: 17px;
    width: 17px;
}

QCheckBox::indicator:hover {
    border-color: #2563EB;
}

QCheckBox::indicator:checked {
    background: #2563EB;
    border-color: #2563EB;
    image: url("__CHECK_ICON_URL__");
}

QRadioButton {
    background: #FFFFFF;
    border: 1px solid #C8D3DF;
    border-radius: 10px;
    color: #101820;
    font-weight: 750;
    padding: 8px 11px;
    spacing: 7px;
}

QRadioButton:hover {
    background: #F8FAFC;
    border-color: #A7B3C2;
}

QRadioButton:checked {
    background: #F8FBFF;
    border-color: #2563EB;
    color: #1D4ED8;
}

QRadioButton::indicator {
    background: #FFFFFF;
    border: 1px solid #A7B3C2;
    border-radius: 7px;
    height: 15px;
    width: 15px;
}

QRadioButton::indicator:checked {
    background: #FFFFFF;
    border: 2px solid #2563EB;
    border-radius: 7px;
    image: url("__RADIO_DOT_ICON_URL__");
}

QPushButton {
    border: none;
    border-radius: 8px;
    font-weight: 750;
    min-height: 30px;
    min-width: 74px;
    padding: 5px 11px;
}

QPushButton:pressed {
    padding-top: 6px;
    padding-bottom: 4px;
}

QPushButton:disabled {
    background: #C8D3DF;
    color: #708195;
}

#primaryButton,
#primaryDialogButton,
#dashboardActionButton[role="primary"],
#rowEditButton,
#smallButton {
    background: #2563EB;
    color: #FFFFFF;
}

#primaryButton:hover,
#primaryDialogButton:hover,
#dashboardActionButton[role="primary"]:hover,
#rowEditButton:hover,
#smallButton:hover {
    background: #1D4ED8;
}

#secondaryButton,
#dashboardActionButton[role="secondary"] {
    background: #0F766E;
    color: #FFFFFF;
}

#secondaryButton:hover,
#dashboardActionButton[role="secondary"]:hover {
    background: #0D5F59;
}

#dangerButton,
#rowDeleteButton {
    background: #DC2626;
    color: #FFFFFF;
}

#dangerButton:hover,
#rowDeleteButton:hover {
    background: #B91C1C;
}

#neutralButton,
#neutralDialogButton {
    background: #E2E8F0;
    color: #101820;
}

#neutralButton:hover,
#neutralDialogButton:hover {
    background: #C8D3DF;
}

#primaryButton,
#secondaryButton,
#dangerButton,
#neutralButton,
#primaryDialogButton,
#neutralDialogButton,
#dashboardActionButton {
    min-height: 32px;
    min-width: 82px;
    padding: 6px 12px;
}

#primaryDialogButton,
#neutralDialogButton {
    min-width: 96px;
    max-width: 150px;
}

#rowEditButton,
#rowDeleteButton,
#smallButton {
    min-height: 28px;
    min-width: 72px;
    padding: 4px 9px;
}

KeypadButton {
    min-height: 46px;
}

ActionButton {
    min-height: 42px;
    padding: 8px 12px;
}

#payButton {
    min-height: 46px;
    font-size: 14px;
}

#splitButton,
#cancelButton {
    min-height: 42px;
}

QTableWidget {
    alternate-background-color: #F8FAFC;
    background: #FFFFFF;
    border: 1px solid #D7DEE8;
    border-radius: 12px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #DBEAFE;
    selection-color: #101820;
}

QHeaderView::section {
    background: #F1F5F9;
    border: none;
    border-bottom: 1px solid #D7DEE8;
    color: #314154;
    font-weight: 800;
    padding: 11px 10px;
}

QTableWidget::item {
    border-bottom: 1px solid #EEF2F7;
    padding: 8px 10px;
}

QTableWidget::item:selected {
    background: #DBEAFE;
    color: #101820;
}

QMessageBox {
    background: #F8FAFC;
}

QMessageBox QLabel {
    background: transparent;
    color: #101820;
    font-size: 13px;
}

QMessageBox QPushButton {
    background: #2563EB;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 750;
    max-width: 110px;
    min-height: 32px;
    min-width: 76px;
    padding: 6px 12px;
}

QMessageBox QPushButton:hover {
    background: #1D4ED8;
}

QScrollBar:vertical {
    background: #F1F5F9;
    border: none;
    width: 12px;
}

QScrollBar::handle:vertical {
    background: #C8D3DF;
    border-radius: 6px;
    min-height: 34px;
}

QScrollBar::handle:vertical:hover {
    background: #A7B3C2;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0;
}
""".replace("__CHECK_ICON_URL__", CHECK_ICON_URL).replace(
    "__RADIO_DOT_ICON_URL__",
    RADIO_DOT_ICON_URL,
)
