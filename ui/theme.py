"""Shared modern UI theme snippets for the POS desktop app."""

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QComboBox, QFrame


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
CHECK_ICON_URL = (ASSETS_DIR / "ui_check.svg").as_posix()
RADIO_DOT_ICON_URL = (ASSETS_DIR / "ui_radio_dot.svg").as_posix()


COMBO_POPUP_STYLESHEET = """
QListView,
QAbstractItemView {
    background: #FFFFFF;
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 0;
    margin: 0;
    outline: 0;
    padding: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QListView::item,
QAbstractItemView::item {
    background: #FFFFFF;
    color: #0F172A;
    min-height: 28px;
    padding: 6px 10px;
}

QListView::item:hover,
QListView::item:selected,
QAbstractItemView::item:hover,
QAbstractItemView::item:selected {
    background: #2563EB;
    color: #FFFFFF;
}
"""


def apply_combobox_popup_fix(combo: QComboBox) -> None:
    """Keep combo popups from showing native black corners on Windows/Fusion."""
    view = combo.view()
    if view is None:
        return

    container = view.parentWidget()
    if container is not None:
        container_palette = container.palette()
        container_palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        container_palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        container.setPalette(container_palette)
        container.setAutoFillBackground(True)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        container.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        container.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        container.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                background-color: #FFFFFF;
                border: none;
                border-radius: 0;
                margin: 0;
                padding: 0;
            }
            """
        )

    if combo.property("_retail_pos_combo_popup_fixed"):
        return

    palette = view.palette()
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Window,
        QPalette.ColorRole.AlternateBase,
    ):
        palette.setColor(role, QColor("#FFFFFF"))
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
    view.setStyleSheet(COMBO_POPUP_STYLESHEET)
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


MODERN_WIDGET_STYLESHEET = """
QWidget {
    color: #0F172A;
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
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #0F172A;
    min-height: 18px;
    padding: 7px 10px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QLineEdit:hover,
QComboBox:hover,
QDateEdit:hover,
QTextEdit:hover {
    border-color: #94A3B8;
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
    border: 1px solid #CBD5E1;
    border-radius: 0;
    outline: 0;
    padding: 0;
    margin: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QComboBox QAbstractItemView::item {
    background: #FFFFFF;
    color: #0F172A;
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
    color: #0F172A;
    font-weight: 650;
    spacing: 7px;
}

QCheckBox::indicator {
    background: #FFFFFF;
    border: 1px solid #94A3B8;
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
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    color: #0F172A;
    font-weight: 750;
    padding: 8px 11px;
    spacing: 7px;
}

QRadioButton:hover {
    background: #F8FAFC;
    border-color: #94A3B8;
}

QRadioButton:checked {
    background: #F8FBFF;
    border-color: #2563EB;
    color: #1D4ED8;
}

QRadioButton::indicator {
    background: #FFFFFF;
    border: 1px solid #94A3B8;
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
    background: #CBD5E1;
    color: #64748B;
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
    color: #0F172A;
}

#neutralButton:hover,
#neutralDialogButton:hover {
    background: #CBD5E1;
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
    selection-color: #0F172A;
}

QHeaderView::section {
    background: #F1F5F9;
    border: none;
    border-bottom: 1px solid #D7DEE8;
    color: #334155;
    font-weight: 800;
    padding: 11px 10px;
}

QTableWidget::item {
    border-bottom: 1px solid #EEF2F7;
    padding: 8px 10px;
}

QTableWidget::item:selected {
    background: #DBEAFE;
    color: #0F172A;
}

QMessageBox {
    background: #F8FAFC;
}

QMessageBox QLabel {
    background: transparent;
    color: #0F172A;
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
    background: #CBD5E1;
    border-radius: 6px;
    min-height: 34px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
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
