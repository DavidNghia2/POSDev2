import secrets
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QDoubleValidator, QPainter, QPixmap
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from database import db
from login import get_setting
from product_management.label_printing import (
    DEFAULT_STICKER_SIZE,
    LABEL_MODE_BARCODE,
    LABEL_MODE_PRICE,
    STICKER_SIZES,
    can_encode_code128,
    configure_sticker_printer,
    render_product_labels,
    sticker_size_options,
)
from ui.currency import DEFAULT_CURRENCY_SYMBOL, format_money, get_currency_symbol_from_settings
from ui.dialogs import confirm_delete
from ui.icon_manager import IconManager
from ui.loading import BlockingTaskRunner, PRODUCT_SYNC_TIMEOUT_MS
from ui.notifications import friendly_error
from ui.theme import THEME_DARK, build_modern_widget_stylesheet, get_theme_mode
from ui.thumbnail_cache import ThumbnailCache

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_TABLE_PAGE_SIZE = 250
ACTION_ICON_BUTTON_SIZE = 32
ACTION_ICON_BUTTON_GAP = 7
ACTION_COLUMN_WIDTH = 124

def build_product_management_stylesheet(mode: str | None = None) -> str:
    active = mode or get_theme_mode()
    if active == THEME_DARK:
        colors = {
            "window_bg": "#0F1520",
            "text": "#E2E8F0",
            "dialog_bg": "#0F1520",
            "title": "#F1F5F9",
            "subtitle": "#94A3B8",
            "section": "#CBD5E1",
            "helper_bg": "#1E3A5F",
            "helper_border": "#2563EB",
            "helper_text": "#93C5FD",
            "panel_bg": "#161D2E",
            "panel_border": "#2D3F5A",
            "dialog_body_bg": "#161D2E",
            "image_bg": "#0F1520",
            "image_border": "#2D3F5A",
            "image_text": "#94A3B8",
            "barcode_row_bg": "#1A2332",
            "barcode_row_border": "#2D3F5A",
            "barcode_value": "#E2E8F0",
            "barcode_variant_bg": "#1E3A8A",
            "barcode_variant_border": "#3B82F6",
            "barcode_variant_text": "#BFDBFE",
            "empty_text": "#64748B",
            "input_bg": "#1A2332",
            "input_border": "#2D3F5A",
            "input_focus": "#3B82F6",
            "neutral_button": "#334155",
            "barcode_delete_bg": "#3B1D24",
            "barcode_delete_text": "#FCA5A5",
            "table_bg": "#161D2E",
            "table_alt": "#0F1520",
            "table_border": "#2D3F5A",
            "table_selection_bg": "#1E3A8A",
            "table_selection_text": "#F1F5F9",
            "table_header_bg": "#1A2332",
            "table_header_text": "#CBD5E1",
            "table_item_border": "#1F2937",
            "table_hover": "#1E2D40",
            "print_hero_bg": "#1B2640",
            "print_hero_border": "#2D3F5A",
            "print_hero_accent": "#3B82F6",
            "print_hero_title": "#F1F5F9",
            "print_hero_text": "#94A3B8",
            "print_badge_bg": "#1E3A8A",
            "print_badge_text": "#93C5FD",
            "print_card_bg": "#1A2332",
            "print_card_border": "#2D3F5A",
            "print_card_title": "#CBD5E1",
            "print_card_text": "#94A3B8",
            "print_preview_bg": "#0F1520",
            "print_preview_border": "#334155",
            "print_preview_title": "#F1F5F9",
            "print_preview_text": "#94A3B8",
            "toolbar_bg": "#161D2E",
            "toolbar_border": "#2D3F5A",
        }
    else:
        colors = {
            "window_bg": "#F1F5F9",
            "text": "#1E293B",
            "dialog_bg": "#F1F5F9",
            "title": "#0F172A",
            "subtitle": "#64748B",
            "section": "#334155",
            "helper_bg": "#EFF6FF",
            "helper_border": "#BFDBFE",
            "helper_text": "#1D4ED8",
            "panel_bg": "#FFFFFF",
            "panel_border": "#E2E8F0",
            "dialog_body_bg": "#FFFFFF",
            "image_bg": "#F8FAFC",
            "image_border": "#E2E8F0",
            "image_text": "#94A3B8",
            "barcode_row_bg": "#F8FAFC",
            "barcode_row_border": "#E2E8F0",
            "barcode_value": "#1E293B",
            "barcode_variant_bg": "#EFF6FF",
            "barcode_variant_border": "#93C5FD",
            "barcode_variant_text": "#1D4ED8",
            "empty_text": "#94A3B8",
            "input_bg": "#FFFFFF",
            "input_border": "#CBD5E1",
            "input_focus": "#3B82F6",
            "neutral_button": "#64748B",
            "barcode_delete_bg": "#FEF2F2",
            "barcode_delete_text": "#DC2626",
            "table_bg": "#FFFFFF",
            "table_alt": "#F8FAFC",
            "table_border": "#E2E8F0",
            "table_selection_bg": "#DBEAFE",
            "table_selection_text": "#0F172A",
            "table_header_bg": "#F1F5F9",
            "table_header_text": "#334155",
            "table_item_border": "#F1F5F9",
            "table_hover": "#F0F6FF",
            "print_hero_bg": "#EFF6FF",
            "print_hero_border": "#BFDBFE",
            "print_hero_accent": "#3B82F6",
            "print_hero_title": "#0F172A",
            "print_hero_text": "#64748B",
            "print_badge_bg": "#EFF6FF",
            "print_badge_text": "#1D4ED8",
            "print_card_bg": "#F8FAFC",
            "print_card_border": "#E2E8F0",
            "print_card_title": "#334155",
            "print_card_text": "#94A3B8",
            "print_preview_bg": "#F8FAFC",
            "print_preview_border": "#CBD5E1",
            "print_preview_title": "#0F172A",
            "print_preview_text": "#94A3B8",
            "toolbar_bg": "#FFFFFF",
            "toolbar_border": "#E2E8F0",
        }

    return f"""
QWidget {{
    background: {colors["window_bg"]};
    color: {colors["text"]};
    font-family: "Segoe UI";
    font-size: 13px;
}}

QDialog {{
    background: {colors["dialog_bg"]};
}}

#titleLabel {{
    color: {colors["title"]};
    font-size: 24px;
    font-weight: 700;
}}

#dialogTitleLabel {{
    color: {colors["title"]};
    font-size: 20px;
    font-weight: 700;
}}

#subtitleLabel {{
    color: {colors["subtitle"]};
    font-size: 13px;
}}

#sectionLabel {{
    color: {colors["section"]};
    font-size: 14px;
    font-weight: 700;
}}

#fieldSectionLabel {{
    color: {colors["section"]};
    font-size: 12px;
    font-weight: 700;
}}

#barcodeRules {{
    background: {colors["helper_bg"]};
    border: 1px solid {colors["helper_border"]};
    border-radius: 8px;
    color: {colors["helper_text"]};
    font-size: 11px;
    font-weight: 600;
    padding: 8px 10px;
}}

#panel, #dialogPanel {{
    background: {colors["panel_bg"]};
    border: 1px solid {colors["panel_border"]};
    border-radius: 14px;
}}

#toolbarWidget {{
    background: {colors["toolbar_bg"]};
    border: 1px solid {colors["toolbar_border"]};
    border-radius: 12px;
}}

#dialogScroll, #dialogBody {{
    background: {colors["dialog_body_bg"]};
    border: none;
}}

QLabel {{
    background: transparent;
}}

#imagePreview, #tableImage {{
    background: {colors["image_bg"]};
    border: 1px solid {colors["image_border"]};
    border-radius: 8px;
    color: {colors["image_text"]};
    font-size: 12px;
    font-weight: 700;
}}

#barcodeScroll {{
    background: {colors["image_bg"]};
    border: 1px solid {colors["image_border"]};
    border-radius: 8px;
}}

#barcodeRow {{
    background: {colors["barcode_row_bg"]};
    border: 1px solid {colors["barcode_row_border"]};
    border-radius: 7px;
}}

#barcodeValue {{
    color: {colors["barcode_value"]};
    font-weight: 700;
}}

#barcodeVariant {{
    background: {colors["barcode_variant_bg"]};
    border: 1px solid {colors["barcode_variant_border"]};
    border-radius: 6px;
    color: {colors["barcode_variant_text"]};
    font-size: 11px;
    font-weight: 800;
    padding: 3px 7px;
}}

#emptyBarcodeLabel {{
    color: {colors["empty_text"]};
    padding: 20px;
}}

QLineEdit, QSpinBox {{
    background: {colors["input_bg"]};
    border: 1px solid {colors["input_border"]};
    border-radius: 8px;
    color: {colors["text"]};
    padding: 10px 12px;
    min-height: 20px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {colors["input_focus"]};
}}

QCheckBox {{
    background: transparent;
    color: {colors["text"]};
    spacing: 8px;
    font-weight: 600;
}}

QPushButton {{
    border: none;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 700;
    min-height: 42px;
    padding: 0 14px;
}}

QPushButton:hover {{
    filter: brightness(1.08);
}}

QPushButton:pressed {{
    padding-top: 13px;
    padding-bottom: 11px;
    filter: brightness(0.95);
}}

#primaryButton, #rowEditButton {{
    background: #2563EB;
}}

#primaryButton:hover, #rowEditButton:hover {{
    background: #1D4ED8;
}}

#secondaryButton {{
    background: #0F766E;
}}

#secondaryButton:hover {{
    background: #0D5F59;
}}

#dangerButton, #rowDeleteButton {{
    background: #DC2626;
}}

#dangerButton:hover, #rowDeleteButton:hover {{
    background: #B91C1C;
}}

#neutralButton {{
    background: {colors["neutral_button"]};
}}

#neutralButton:hover {{
    background: #475569;
}}

#smallButton {{
    background: #2563EB;
    min-width: 104px;
    padding: 0 12px;
}}

#smallButton:hover {{
    background: #1D4ED8;
}}

#barcodeDeleteButton {{
    background: {colors["barcode_delete_bg"]};
    color: {colors["barcode_delete_text"]};
    border-radius: 6px;
    padding: 0;
}}

#barcodeDeleteButton:hover {{
    background: #DC2626;
    color: #FFFFFF;
}}

#rowEditButton, #rowDeleteButton {{
    min-height: 32px;
    padding: 0 10px;
}}

QTableView {{
    background: {colors["table_bg"]};
    border: 1px solid {colors["table_border"]};
    border-radius: 10px;
    alternate-background-color: {colors["table_alt"]};
    gridline-color: transparent;
    color: {colors["text"]};
    selection-background-color: {colors["table_selection_bg"]};
    selection-color: {colors["table_selection_text"]};
}}

QHeaderView::section {{
    background: {colors["table_header_bg"]};
    border: none;
    border-bottom: 1px solid {colors["table_border"]};
    color: {colors["table_header_text"]};
    font-weight: 700;
    padding: 12px 10px;
}}

QTableView::item {{
    border-bottom: 1px solid {colors["table_item_border"]};
    color: {colors["text"]};
    padding: 8px;
}}

QTableView::item:selected {{
    background: {colors["table_selection_bg"]};
    color: {colors["table_selection_text"]};
}}

QTableView::item:hover {{
    background: {colors["table_hover"]};
}}

#printHero {{
    background: {colors["print_hero_bg"]};
    border: 1px solid {colors["print_hero_border"]};
    border-left: 4px solid {colors["print_hero_accent"]};
    border-radius: 14px;
}}

#printProductName {{
    color: {colors["print_hero_title"]};
    font-size: 18px;
    font-weight: 800;
}}

#printProductMeta {{
    color: {colors["print_hero_text"]};
    font-size: 12px;
    font-weight: 500;
}}

#printPriceBadge {{
    background: {colors["print_badge_bg"]};
    border: 1px solid {colors["print_hero_border"]};
    border-radius: 10px;
    color: {colors["print_badge_text"]};
    font-size: 16px;
    font-weight: 900;
    padding: 6px 14px;
}}

#printOptionCard {{
    background: {colors["print_card_bg"]};
    border: 1px solid {colors["print_card_border"]};
    border-radius: 12px;
}}

#printSectionTitle {{
    color: {colors["print_card_title"]};
    font-size: 13px;
    font-weight: 800;
}}

#printSectionHint {{
    color: {colors["print_card_text"]};
    font-size: 12px;
    font-weight: 500;
}}

#printPreviewCard {{
    background: {colors["print_preview_bg"]};
    border: 1px solid {colors["print_preview_border"]};
    border-radius: 12px;
}}

#printPreviewTitle {{
    color: {colors["print_preview_title"]};
    font-size: 12px;
    font-weight: 800;
}}

#printPreviewBody {{
    color: {colors["print_preview_text"]};
    font-size: 11px;
    font-weight: 500;
}}

QLabel#printFormLabel {{
    color: {colors["section"]};
    font-size: 12px;
    font-weight: 700;
}}

QComboBox, QSpinBox {{
    min-height: 26px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    width: 20px;
}}

QSpinBox::up-arrow, QSpinBox::down-arrow {{
    width: 0;
    height: 0;
}}

QPushButton#printWideButton {{
    min-height: 38px;
}}

QRadioButton {{
    background: {colors["panel_bg"]};
    border: 1px solid {colors["panel_border"]};
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}}

QRadioButton:hover {{
    border-color: {colors["input_focus"]};
}}

QRadioButton:checked {{
    background: {colors["helper_bg"]};
    border: 1px solid {colors["input_focus"]};
}}
""" + build_modern_widget_stylesheet(active)

def format_barcodes_for_display(barcodes: list[str]) -> str:
    if not barcodes:
        return ""
    if len(barcodes) <= 3:
        return ", ".join(barcodes)
    return f"{barcodes[0]} + {len(barcodes) - 1} more"


def set_label_pixmap(
    label: QLabel,
    image_path: str,
    fallback_text: str,
    width: int,
    height: int,
) -> None:
    pixmap = ThumbnailCache.get(image_path, width, height, PROJECT_ROOT)
    if not pixmap.isNull():
        label.setPixmap(pixmap)
        label.setText("")
        return
    label.setPixmap(QPixmap())
    label.setText(fallback_text)


class ProductTableModel(QAbstractTableModel):
    HEADERS = [
        "No",
        "Image",
        "Product Name",
        "Barcodes",
        "Price",
        "Stock",
        "Category",
        "Requires Weight",
        "Cloud Status",
        "Actions",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.products: list[dict] = []
        self.offset = 0
        self.currency_symbol = DEFAULT_CURRENCY_SYMBOL

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.products)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        product = self.products[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return int(product["id"])

        if role == Qt.ItemDataRole.DecorationRole and column == 1:
            pixmap = ThumbnailCache.get(str(product.get("image_path") or ""), 64, 48, PROJECT_ROOT)
            return pixmap if not pixmap.isNull() else None

        if role == Qt.ItemDataRole.DisplayRole:
            barcodes = list(product.get("barcodes") or [])
            sync_status = str(product.get("sync_status") or "local")
            sync_error = str(product.get("sync_error") or "")
            status_text = "Error" if sync_error else sync_status.title()
            values = {
                0: str(self.offset + index.row() + 1),
                1: "No Image" if not str(product.get("image_path") or "") else "",
                2: product["name"] or "",
                3: format_barcodes_for_display(barcodes),
                4: format_money(float(product["price"]), self.currency_symbol),
                5: f'{float(product.get("stock_qty") or 0):g}',
                6: product["category"] or "",
                7: "Yes" if product["requires_weight"] else "No",
                8: status_text,
                9: "",
            }
            return values.get(column, "")

        if role == Qt.ItemDataRole.ToolTipRole:
            sync_error = str(product.get("sync_error") or "")
            sync_status = str(product.get("sync_status") or "")
            if column == 8:
                if sync_error:
                    return friendly_error(sync_error)
                return sync_status
            if column == 9:
                retry_hint = "Retry sync available" if sync_status == "pending" or sync_error else "Retry disabled"
                return f"Edit product | {retry_hint} | Delete product"

        if role == Qt.ItemDataRole.ForegroundRole and column == 8:
            sync_error = str(product.get("sync_error") or "")
            sync_status = str(product.get("sync_status") or "")
            if sync_error:
                return QColor("#B91C1C")
            if sync_status == "synced":
                return QColor("#047857")
            if sync_status == "pending":
                return QColor("#B45309")

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (2, 3, 6):
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.SizeHintRole:
            if column == 1:
                return QSize(70, 54)
            if column == 9:
                return QSize(ACTION_COLUMN_WIDTH, 54)

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_products(self, products: list[dict], offset: int) -> None:
        self.beginResetModel()
        self.products = products
        self.offset = offset
        self.endResetModel()

    def set_currency_symbol(self, currency_symbol: str) -> None:
        if self.currency_symbol == currency_symbol:
            return
        self.currency_symbol = currency_symbol
        if not self.products:
            return
        top_left = self.index(0, 4)
        bottom_right = self.index(len(self.products) - 1, 4)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole])

    def product_id_at(self, row: int) -> int | None:
        if row < 0 or row >= len(self.products):
            return None
        return int(self.products[row]["id"])

    def product_sync_status_at(self, row: int) -> tuple[str, str]:
        if row < 0 or row >= len(self.products):
            return "", ""
        product = self.products[row]
        return str(product.get("sync_status") or ""), str(product.get("sync_error") or "")


class ProductActionsDelegate(QStyledItemDelegate):
    edit_requested = pyqtSignal(int)
    retry_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        if option.state & QStyle.StateFlag.State_Selected:
            selection_color = "#274B7A" if get_theme_mode() == THEME_DARK else "#DBEAFE"
            painter.fillRect(option.rect, QColor(selection_color))

        model = index.model()
        edit_rect, retry_rect, delete_rect = self.action_rects(option.rect)
        sync_status, sync_error = model.product_sync_status_at(index.row())
        retry_enabled = sync_status == "pending" or bool(sync_error)
        retry_color = "#F59E0B" if retry_enabled else self.inactive_button_color()
        retry_icon_color = "#FFFFFF" if retry_enabled else self.inactive_icon_color()

        self.draw_action_button(painter, edit_rect, "edit", "#2563EB")
        self.draw_action_button(painter, retry_rect, "refresh", retry_color, retry_icon_color)
        self.draw_action_button(painter, delete_rect, "delete", "#DC2626")

    def editorEvent(self, event, model, option, index: QModelIndex) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        edit_rect, retry_rect, delete_rect = self.action_rects(option.rect)
        product_id = model.product_id_at(index.row())
        if product_id is None:
            return False

        if edit_rect.contains(position):
            self.edit_requested.emit(product_id)
            return True
        if retry_rect.contains(position):
            sync_status, sync_error = model.product_sync_status_at(index.row())
            if sync_status == "pending" or sync_error:
                self.retry_requested.emit(product_id)
            return True
        if delete_rect.contains(position):
            self.delete_requested.emit(product_id)
            return True
        return False

    def action_rects(self, cell_rect: QRect) -> tuple[QRect, QRect, QRect]:
        button_size = ACTION_ICON_BUTTON_SIZE
        gap = ACTION_ICON_BUTTON_GAP
        total_width = (button_size * 3) + (gap * 2)
        left = cell_rect.left() + max((cell_rect.width() - total_width) // 2, 6)
        top = cell_rect.top() + max((cell_rect.height() - button_size) // 2, 4)
        edit_rect = QRect(left, top, button_size, button_size)
        retry_rect = QRect(left + button_size + gap, top, button_size, button_size)
        delete_rect = QRect(left + ((button_size + gap) * 2), top, button_size, button_size)
        return edit_rect, retry_rect, delete_rect

    def draw_action_button(
        self,
        painter: QPainter,
        rect: QRect,
        icon_key: str,
        background_color: str,
        icon_color: str = "#FFFFFF",
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background_color))
        painter.drawRoundedRect(rect, 8, 8)

        icon_size = 17
        icon_rect = QRect(
            rect.center().x() - (icon_size // 2),
            rect.center().y() - (icon_size // 2),
            icon_size,
            icon_size,
        )
        painter.drawPixmap(icon_rect, IconManager.pixmap(icon_key, icon_size, icon_color))
        painter.restore()

    def inactive_button_color(self) -> str:
        return "#314154" if get_theme_mode() == THEME_DARK else "#E2E8F0"

    def inactive_icon_color(self) -> str:
        return "#A7B3C2" if get_theme_mode() == THEME_DARK else "#64748B"


class ProductDialog(QDialog):
    def __init__(self, product: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.product_id = int(product["id"]) if product is not None else None
        self.image_path = str(product.get("image_path") or "") if product is not None else ""
        self.barcodes = list(product.get("barcodes") or []) if product is not None else []
        self.save_task_runner = BlockingTaskRunner(self, timeout_ms=PRODUCT_SYNC_TIMEOUT_MS)

        self.setWindowTitle("Edit Product" if product is not None else "Add Product")
        self.setModal(True)
        self.resize(620, 760)
        self.setMinimumSize(560, 620)
        self.apply_styles()

        self.create_ui()
        if product is not None:
            self.populate_form(product)
        self.render_barcode_list()

    def apply_styles(self) -> None:
        self.setStyleSheet(build_product_management_stylesheet())

    def create_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        dialog_panel = QFrame()
        dialog_panel.setObjectName("dialogPanel")
        panel_layout = QVBoxLayout(dialog_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        root_layout.addWidget(dialog_panel, 1)

        dialog_scroll = QScrollArea()
        dialog_scroll.setObjectName("dialogScroll")
        dialog_scroll.setWidgetResizable(True)
        dialog_scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(dialog_scroll)

        dialog_body = QWidget()
        dialog_body.setObjectName("dialogBody")
        dialog_scroll.setWidget(dialog_body)

        layout = QVBoxLayout(dialog_body)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title_text = "Edit Product" if self.product_id is not None else "Add Product"
        title_label = IconManager.label(title_text, "products", "dialogTitleLabel", icon_size=20)
        layout.addWidget(title_label)

        self.image_preview = QLabel("No Image")
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFixedHeight(145)
        layout.addWidget(self.image_preview)

        choose_image_button = QPushButton("Choose Image")
        IconManager.apply_button(choose_image_button, "upload", IconManager.LIGHT)
        choose_image_button.setObjectName("secondaryButton")
        choose_image_button.clicked.connect(self.choose_image)
        layout.addWidget(choose_image_button)

        barcode_section = QVBoxLayout()
        barcode_section.setContentsMargins(0, 4, 0, 0)
        barcode_section.setSpacing(8)

        barcode_label = IconManager.label("Barcodes", "barcode", "fieldSectionLabel", icon_size=16)
        barcode_section.addWidget(barcode_label)

        barcode_rules = QLabel(
            "Rule: barcodes belong to this product. The first barcode is primary; POS can scan any barcode."
        )
        barcode_rules.setObjectName("barcodeRules")
        barcode_rules.setWordWrap(True)
        barcode_section.addWidget(barcode_rules)

        barcode_input_row = QHBoxLayout()
        barcode_input_row.setSpacing(8)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Barcode")
        self.barcode_input.returnPressed.connect(self.add_barcode_from_input)

        add_barcode_button = QPushButton("Add Barcode")
        IconManager.apply_button(add_barcode_button, "add", IconManager.LIGHT)
        add_barcode_button.setObjectName("smallButton")
        add_barcode_button.clicked.connect(self.add_barcode_from_input)

        barcode_input_row.addWidget(self.barcode_input, 1)
        barcode_input_row.addWidget(add_barcode_button)
        barcode_section.addLayout(barcode_input_row)

        self.barcode_list_widget = QWidget()
        self.barcode_list_layout = QVBoxLayout(self.barcode_list_widget)
        self.barcode_list_layout.setContentsMargins(0, 0, 0, 0)
        self.barcode_list_layout.setSpacing(6)

        barcode_scroll = QScrollArea()
        barcode_scroll.setObjectName("barcodeScroll")
        barcode_scroll.setWidgetResizable(True)
        barcode_scroll.setFrameShape(QFrame.Shape.NoFrame)
        barcode_scroll.setFixedHeight(120)
        barcode_scroll.setWidget(self.barcode_list_widget)
        barcode_section.addWidget(barcode_scroll)
        layout.addLayout(barcode_section)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setContentsMargins(0, 2, 0, 0)
        layout.addLayout(form_layout)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product Name")

        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Price")
        self.price_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Category")

        self.stock_input = QLineEdit()
        self.stock_input.setPlaceholderText("Stock Quantity")
        self.stock_input.setText("0")
        self.stock_input.setValidator(QDoubleValidator(0.0, 999999999.0, 3))

        self.requires_weight_checkbox = QCheckBox()

        form_layout.addRow("Product Name", self.name_input)
        form_layout.addRow("Price", self.price_input)
        form_layout.addRow("Category", self.category_input)
        form_layout.addRow("Stock Quantity", self.stock_input)
        form_layout.addRow("Requires Weight", self.requires_weight_checkbox)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(10)
        button_layout.addStretch(1)

        self.cancel_button = QPushButton("Cancel")
        IconManager.apply_button(self.cancel_button, "cancel", IconManager.LIGHT)
        self.cancel_button.setObjectName("neutralButton")
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save")
        IconManager.apply_button(self.save_button, "save", IconManager.LIGHT)
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_product)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

        self.update_image_preview()

    def populate_form(self, product: dict) -> None:
        self.name_input.setText(str(product.get("name") or ""))
        self.price_input.setText(f'{float(product["price"]):.2f}')
        self.category_input.setText(str(product.get("category") or ""))
        self.stock_input.setText(f'{float(product.get("stock_qty") or 0):g}')
        self.requires_weight_checkbox.setChecked(bool(product.get("requires_weight")))
        self.update_image_preview()

    def save_product(self) -> None:
        form_data = self.get_form_data(include_pending_barcode=True)
        if form_data is None:
            return

        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        def save_task() -> int:
            return db.save_product_cloud_required(self.product_id, *form_data)

        def on_success(saved_product_id: int) -> None:
            self.product_id = saved_product_id
            self.accept()

        def on_error(error: Exception) -> None:
            self.save_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            if isinstance(error, sqlite3.IntegrityError):
                self.show_error("A product with one of these barcodes already exists.")
                return
            self.show_error(friendly_error(error))

        if not self.save_task_runner.start(
            task=save_task,
            message="Saving product to cloud...",
            on_success=on_success,
            on_error=on_error,
            timeout_ms=PRODUCT_SYNC_TIMEOUT_MS,
            timeout_message="Product sync is taking too long. Please check the network and try again.",
        ):
            self.save_button.setEnabled(True)
            self.cancel_button.setEnabled(True)

    def get_form_data(
        self,
        include_pending_barcode: bool = False,
    ) -> tuple[str, float, str, float, bool, str, list[str]] | None:
        pending_barcode = self.barcode_input.text().strip()
        barcodes = list(self.barcodes)
        if include_pending_barcode and pending_barcode:
            clean_barcode = pending_barcode.strip()
            if not self.can_add_barcode(clean_barcode):
                return None
            barcodes.append(clean_barcode)

        name = self.name_input.text().strip()
        price_text = self.price_input.text().strip()
        category = self.category_input.text().strip()
        stock_text = self.stock_input.text().strip()
        requires_weight = self.requires_weight_checkbox.isChecked()

        if not name:
            self.show_error("Product Name is required.")
            return None

        try:
            price = float(price_text)
            if price < 0:
                raise ValueError
        except ValueError:
            self.show_error("Please enter a valid price.")
            return None

        try:
            stock_qty = float(stock_text)
            if stock_qty < 0:
                raise ValueError
        except ValueError:
            self.show_error("Please enter a valid stock quantity.")
            return None

        return name, price, category, stock_qty, requires_weight, self.image_path, barcodes

    def choose_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Product Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
        )
        if not file_path:
            return
        self.image_path = file_path
        self.update_image_preview()

    def add_barcode_from_input(self) -> None:
        self.add_barcode(self.barcode_input.text().strip())

    def add_barcode(self, barcode: str) -> bool:
        clean_barcode = barcode.strip()
        if not clean_barcode:
            return True
        if not self.can_add_barcode(clean_barcode):
            return False
        self.barcodes.append(clean_barcode)
        self.barcode_input.clear()
        self.render_barcode_list()
        return True

    def can_add_barcode(self, barcode: str) -> bool:
        clean_barcode = barcode.strip()
        if clean_barcode in self.barcodes:
            self.show_error("This barcode is already in the list.")
            return False
        if db.barcode_exists(clean_barcode, self.product_id):
            self.show_error("This barcode is already assigned to another product.")
            return False
        return True

    def remove_barcode(self, barcode: str) -> None:
        self.barcodes = [item for item in self.barcodes if item != barcode]
        self.render_barcode_list()

    def render_barcode_list(self) -> None:
        while self.barcode_list_layout.count():
            item = self.barcode_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.barcodes:
            empty_label = QLabel("No barcodes added")
            empty_label.setObjectName("emptyBarcodeLabel")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.barcode_list_layout.addWidget(empty_label)
        else:
            for barcode in self.barcodes:
                self.barcode_list_layout.addWidget(self.create_barcode_row(barcode))
        self.barcode_list_layout.addStretch()

    def create_barcode_row(self, barcode: str) -> QWidget:
        row = QFrame()
        row.setObjectName("barcodeRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 6, 6, 6)
        row_layout.setSpacing(8)

        label = QLabel(barcode)
        label.setObjectName("barcodeValue")
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        variant_label = QLabel("Primary" if self.barcodes.index(barcode) == 0 else "Linked")
        variant_label.setObjectName("barcodeVariant")

        delete_button = QPushButton()
        delete_button.setObjectName("barcodeDeleteButton")
        delete_button.setToolTip("Remove barcode")
        delete_button.setFixedSize(26, 24)
        IconManager.apply_button(delete_button, "delete", IconManager.DARK, size=16)
        delete_button.clicked.connect(lambda _checked=False, value=barcode: self.remove_barcode(value))

        row_layout.addWidget(label, 1)
        row_layout.addWidget(variant_label)
        row_layout.addWidget(delete_button)
        return row

    def update_image_preview(self) -> None:
        set_label_pixmap(self.image_preview, self.image_path, "No Image", 520, 140)

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Validation Error", message)


class ProductLabelPrintDialog(QDialog):
    def __init__(
        self,
        product: dict,
        currency_symbol: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.product = dict(product)
        self.currency_symbol = currency_symbol
        self.product_updated = False
        self.save_task_runner = BlockingTaskRunner(self, timeout_ms=PRODUCT_SYNC_TIMEOUT_MS)

        self.setWindowTitle("Print Product Label")
        self.setModal(True)
        self.resize(560, 460)
        self.setMinimumWidth(520)
        self.apply_styles()
        self.create_ui()
        self.refresh_barcode_controls()
        self.update_size_description()
        self.update_mode_state()

    @property
    def barcodes(self) -> list[str]:
        return list(self.product.get("barcodes") or [])

    def apply_styles(self) -> None:
        self.setStyleSheet(build_product_management_stylesheet())

    def create_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("dialogPanel")
        root_layout.addWidget(panel, 1)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title_label = IconManager.label("Print Product Label", "print", "dialogTitleLabel", icon_size=22)
        layout.addWidget(title_label)

        product_name = str(self.product.get("name") or "Product")
        price_text = self.current_price_text()

        hero = QFrame()
        hero.setObjectName("printHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(12)

        product_info_layout = QVBoxLayout()
        product_info_layout.setContentsMargins(0, 0, 0, 0)
        product_info_layout.setSpacing(3)

        product_name_label = QLabel(product_name)
        product_name_label.setObjectName("printProductName")
        product_name_label.setWordWrap(True)

        barcode_count = len(self.barcodes)
        meta_text = f"{barcode_count} barcode{'s' if barcode_count != 1 else ''} available · Ready to print labels"
        product_meta_label = QLabel(meta_text)
        product_meta_label.setObjectName("printProductMeta")
        product_meta_label.setWordWrap(True)

        product_info_layout.addWidget(product_name_label)
        product_info_layout.addWidget(product_meta_label)

        price_badge = QLabel(price_text)
        price_badge.setObjectName("printPriceBadge")
        price_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        price_badge.setMinimumWidth(128)

        hero_layout.addLayout(product_info_layout, 1)
        hero_layout.addWidget(price_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hero)

        mode_card = QFrame()
        mode_card.setObjectName("printOptionCard")
        mode_card_layout = QVBoxLayout(mode_card)
        mode_card_layout.setContentsMargins(14, 12, 14, 12)
        mode_card_layout.setSpacing(8)

        mode_title = QLabel("Choose label type")
        mode_title.setObjectName("printSectionTitle")
        mode_hint = QLabel("Print a scannable barcode sticker or a clean shelf price label.")
        mode_hint.setObjectName("printSectionHint")
        mode_hint.setWordWrap(True)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self.barcode_mode_radio = QRadioButton("Barcode")
        self.price_mode_radio = QRadioButton("Price Label")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.barcode_mode_radio, 0)
        self.mode_group.addButton(self.price_mode_radio, 1)
        self.barcode_mode_radio.setChecked(True)
        self.barcode_mode_radio.toggled.connect(self.update_mode_state)
        self.price_mode_radio.toggled.connect(self.update_mode_state)
        mode_row.addWidget(self.barcode_mode_radio)
        mode_row.addWidget(self.price_mode_radio)
        mode_row.addStretch(1)

        mode_card_layout.addWidget(mode_title)
        mode_card_layout.addWidget(mode_hint)
        mode_card_layout.addLayout(mode_row)
        layout.addWidget(mode_card)

        settings_card = QFrame()
        settings_card.setObjectName("printOptionCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(14, 12, 14, 12)
        settings_layout.setSpacing(8)

        settings_title = QLabel("Print settings")
        settings_title.setObjectName("printSectionTitle")
        settings_layout.addWidget(settings_title)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(12)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        settings_layout.addLayout(form_layout)

        self.size_combo = QComboBox()
        for key, label in sticker_size_options():
            self.size_combo.addItem(label, key)
        default_index = self.size_combo.findData(DEFAULT_STICKER_SIZE)
        if default_index >= 0:
            self.size_combo.setCurrentIndex(default_index)
        self.size_combo.currentIndexChanged.connect(self.update_size_description)
        self.size_combo.currentIndexChanged.connect(self.update_preview_summary)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999)
        self.quantity_spin.setValue(1)
        self.quantity_spin.valueChanged.connect(self.update_preview_summary)

        self.barcode_combo = QComboBox()
        self.barcode_combo.currentIndexChanged.connect(self.update_preview_summary)

        self.generate_barcode_button = QPushButton("Generate Barcode")
        self.generate_barcode_button.setObjectName("secondaryButton")
        self.generate_barcode_button.setProperty("class", "printWideButton")
        IconManager.apply_button(self.generate_barcode_button, "barcode", IconManager.LIGHT)
        self.generate_barcode_button.clicked.connect(self.generate_barcode)

        self.barcode_field_label = QLabel("Barcode")
        self.generate_barcode_field_label = QLabel("")
        for field_label in (self.barcode_field_label, self.generate_barcode_field_label):
            field_label.setObjectName("printFormLabel")

        size_label = QLabel("Sticker Size")
        quantity_label = QLabel("Quantity")
        for field_label in (size_label, quantity_label):
            field_label.setObjectName("printFormLabel")

        form_layout.addRow(size_label, self.size_combo)
        form_layout.addRow(quantity_label, self.quantity_spin)
        form_layout.addRow(self.barcode_field_label, self.barcode_combo)
        form_layout.addRow(self.generate_barcode_field_label, self.generate_barcode_button)

        self.size_help_label = QLabel("")
        self.size_help_label.setObjectName("printSectionHint")
        self.size_help_label.setWordWrap(True)
        settings_layout.addWidget(self.size_help_label)
        layout.addWidget(settings_card)

        preview_card = QFrame()
        preview_card.setObjectName("printPreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 10, 14, 10)
        preview_layout.setSpacing(4)

        preview_title = QLabel("Label preview summary")
        preview_title.setObjectName("printPreviewTitle")
        self.preview_summary_label = QLabel("")
        self.preview_summary_label.setObjectName("printPreviewBody")
        self.preview_summary_label.setWordWrap(True)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview_summary_label)
        layout.addWidget(preview_card)

        layout.addStretch(1)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.setSpacing(10)
        button_layout.addStretch(1)

        close_button = QPushButton("Close")
        close_button.setObjectName("neutralButton")
        IconManager.apply_button(close_button, "cancel", IconManager.LIGHT)
        close_button.clicked.connect(self.reject)

        self.preview_button = QPushButton("Preview / Print")
        self.preview_button.setObjectName("primaryButton")
        IconManager.apply_button(self.preview_button, "print", IconManager.LIGHT)
        self.preview_button.clicked.connect(self.preview_labels)

        button_layout.addWidget(close_button)
        button_layout.addWidget(self.preview_button)
        layout.addLayout(button_layout)

    def refresh_barcode_controls(self) -> None:
        current_barcode = str(self.barcode_combo.currentData() or "").strip() if hasattr(self, "barcode_combo") else ""
        self.barcode_combo.clear()
        for index, barcode in enumerate(self.barcodes):
            label = f"{barcode} (Primary)" if index == 0 else barcode
            self.barcode_combo.addItem(label, barcode)
        if current_barcode:
            index = self.barcode_combo.findData(current_barcode)
            if index >= 0:
                self.barcode_combo.setCurrentIndex(index)

    def update_mode_state(self, *_args) -> None:
        is_barcode_mode = self.selected_label_mode() == LABEL_MODE_BARCODE
        has_barcodes = bool(self.barcodes)
        self.barcode_field_label.setVisible(is_barcode_mode)
        self.barcode_combo.setVisible(is_barcode_mode)
        self.generate_barcode_field_label.setVisible(is_barcode_mode and not has_barcodes)
        self.barcode_combo.setEnabled(is_barcode_mode and has_barcodes)
        self.generate_barcode_button.setVisible(is_barcode_mode and not has_barcodes)
        self.update_preview_summary()

    def update_preview_summary(self, *_args) -> None:
        mode = self.selected_label_mode()
        size_key = self.current_sticker_size_key()
        size_info = STICKER_SIZES.get(size_key, STICKER_SIZES[DEFAULT_STICKER_SIZE])
        quantity = self.quantity_spin.value()
        barcode = self.current_barcode()
        width = float(size_info["width_mm"])
        height = float(size_info["height_mm"])
        size_label = str(size_info["label"])

        if mode == LABEL_MODE_BARCODE:
            barcode_preview = barcode if barcode else "No barcode selected"
            summary = (
                f"Barcode sticker · {size_label} ({width:g}x{height:g} mm) · "
                f"{quantity} copy{'ies' if quantity != 1 else ''}\n"
                f"Barcode: {barcode_preview}"
            )
        else:
            summary = (
                f"Price label · {size_label} ({width:g}x{height:g} mm) · "
                f"{quantity} copy{'ies' if quantity != 1 else ''}\n"
                f"Shows product name and price"
            )
        self.preview_summary_label.setText(summary)

    def update_size_description(self, *_args) -> None:
        size_key = self.current_sticker_size_key()
        size_info = STICKER_SIZES.get(size_key, STICKER_SIZES[DEFAULT_STICKER_SIZE])
        self.size_help_label.setText(str(size_info["description"]))

    def selected_label_mode(self) -> str:
        if self.price_mode_radio.isChecked():
            return LABEL_MODE_PRICE
        return LABEL_MODE_BARCODE

    def current_sticker_size_key(self) -> str:
        return str(self.size_combo.currentData() or DEFAULT_STICKER_SIZE)

    def current_barcode(self) -> str:
        return str(self.barcode_combo.currentData() or "").strip()

    def current_price_text(self) -> str:
        return format_money(float(self.product.get("price") or 0), self.currency_symbol)

    def generate_barcode(self) -> None:
        product_id = int(self.product["id"])
        barcode = generate_unique_internal_barcode(product_id)
        updated_barcodes = [*self.barcodes, barcode]
        self.generate_barcode_button.setEnabled(False)
        self.preview_button.setEnabled(False)

        def save_task() -> int:
            return db.save_product_cloud_required(
                product_id,
                str(self.product.get("name") or ""),
                float(self.product.get("price") or 0),
                str(self.product.get("category") or ""),
                float(self.product.get("stock_qty") or 0),
                bool(self.product.get("requires_weight")),
                str(self.product.get("image_path") or ""),
                updated_barcodes,
            )

        def on_success(saved_product_id: int) -> None:
            refreshed_product = db.get_product_by_id(saved_product_id)
            if refreshed_product is not None:
                self.product = refreshed_product
            else:
                self.product["barcodes"] = updated_barcodes
                self.product["barcode"] = updated_barcodes[0]
                self.product["primary_barcode"] = updated_barcodes[0]
            self.product_updated = True
            self.refresh_barcode_controls()
            self.update_mode_state()
            self.generate_barcode_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            QMessageBox.information(self, "Barcode Generated", f"Generated barcode: {barcode}")

        def on_error(error: Exception) -> None:
            self.generate_barcode_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            if isinstance(error, sqlite3.IntegrityError):
                QMessageBox.warning(self, "Barcode Error", "Generated barcode already exists. Please try again.")
                return
            QMessageBox.warning(self, "Barcode Sync Error", friendly_error(error))

        if not self.save_task_runner.start(
            task=save_task,
            message="Saving generated barcode...",
            on_success=on_success,
            on_error=on_error,
            timeout_ms=PRODUCT_SYNC_TIMEOUT_MS,
            timeout_message="Barcode sync is taking too long. Please check the network and try again.",
        ):
            self.generate_barcode_button.setEnabled(True)
            self.preview_button.setEnabled(True)

    def preview_labels(self) -> None:
        mode = self.selected_label_mode()
        barcode = self.current_barcode()
        if mode == LABEL_MODE_BARCODE:
            if not barcode:
                QMessageBox.warning(
                    self,
                    "Barcode Required",
                    "Generate a barcode before printing a barcode sticker.",
                )
                return
            if not can_encode_code128(barcode):
                QMessageBox.warning(
                    self,
                    "Unsupported Barcode",
                    "Barcode can only contain standard printable characters for Code128.",
                )
                return

        product_name = str(self.product.get("name") or "Product")
        price_text = self.current_price_text()
        size_key = self.current_sticker_size_key()
        quantity = self.quantity_spin.value()
        doc_name = "Barcode Label" if mode == LABEL_MODE_BARCODE else "Price Label"

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_sticker_printer(printer, size_key, doc_name)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle(f"Print Preview - {doc_name}")
        preview.resize(720, 520)
        preview.paintRequested.connect(
            lambda preview_printer: render_product_labels(
                preview_printer,
                mode,
                product_name,
                price_text,
                barcode,
                size_key,
                quantity,
            )
        )
        preview.exec()


def generate_unique_internal_barcode(product_id: int) -> str:
    for _attempt in range(100):
        candidate = f"20{product_id:06d}{secrets.randbelow(1_000_000):06d}"
        if not db.barcode_exists(candidate, exclude_product_id=product_id):
            return candidate
    raise RuntimeError("Could not generate a unique barcode. Please try again.")


class ProductManagementWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        db.init_db()
        self.current_offset = 0
        self.page_size = PRODUCT_TABLE_PAGE_SIZE
        self.total_products = 0
        self.products_loaded = False
        self.blocking_task_runner = BlockingTaskRunner(self, timeout_ms=PRODUCT_SYNC_TIMEOUT_MS)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.apply_search_filter)
        self.create_ui()
        self.apply_styles()
        self.load_products()

    def create_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 28)
        root_layout.setSpacing(16)

        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("toolbarWidget")
        toolbar_frame_layout = QHBoxLayout(toolbar_frame)
        toolbar_frame_layout.setContentsMargins(14, 8, 14, 8)
        toolbar_frame_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Product Name or any Barcode...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.schedule_search)

        add_button = QPushButton("Add Product")
        add_button.setObjectName("primaryButton")
        IconManager.apply_button(add_button, "add", IconManager.LIGHT)
        add_button.clicked.connect(self.open_add_dialog)

        self.print_label_button = QPushButton("Print Label")
        self.print_label_button.setObjectName("secondaryButton")
        self.print_label_button.setEnabled(False)
        IconManager.apply_button(self.print_label_button, "print", IconManager.LIGHT)
        self.print_label_button.clicked.connect(self.open_print_label_dialog)

        toolbar_frame_layout.addWidget(self.search_input, 1)
        toolbar_frame_layout.addWidget(self.print_label_button)
        toolbar_frame_layout.addWidget(add_button)
        root_layout.addWidget(toolbar_frame)
        root_layout.addWidget(self.create_table_panel(), 1)

    def create_table_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.products_model = ProductTableModel(self)
        self.products_table = QTableView()
        self.products_table.setModel(self.products_model)
        self.products_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.products_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.products_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setShowGrid(False)
        self.products_table.setWordWrap(False)
        self.products_table.setIconSize(QSize(64, 48))
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.verticalHeader().setDefaultSectionSize(68)
        self.products_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.products_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.products_table.selectionModel().selectionChanged.connect(self.update_print_label_button_state)

        header = self.products_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.products_table.setColumnWidth(1, 82)
        self.products_table.setColumnWidth(3, 220)
        self.products_table.setColumnWidth(8, 120)
        self.products_table.setColumnWidth(9, ACTION_COLUMN_WIDTH)

        actions_delegate = ProductActionsDelegate(self.products_table)
        actions_delegate.edit_requested.connect(self.open_edit_dialog)
        actions_delegate.retry_requested.connect(self.retry_product_sync)
        actions_delegate.delete_requested.connect(self.delete_product)
        self.products_table.setItemDelegateForColumn(9, actions_delegate)
        self.actions_delegate = actions_delegate

        layout.addWidget(self.products_table, 1)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(10)

        self.pagination_label = QLabel("")
        self.pagination_label.setObjectName("subtitleLabel")

        self.previous_page_button = QPushButton("Previous")
        self.previous_page_button.setObjectName("neutralButton")
        self.previous_page_button.clicked.connect(self.previous_page)

        self.next_page_button = QPushButton("Next")
        self.next_page_button.setObjectName("primaryButton")
        self.next_page_button.clicked.connect(self.next_page)

        pagination_layout.addWidget(self.pagination_label, 1)
        pagination_layout.addWidget(self.previous_page_button)
        pagination_layout.addWidget(self.next_page_button)
        layout.addLayout(pagination_layout)
        return panel

    def schedule_search(self) -> None:
        self.current_offset = 0
        self.search_timer.start()

    def apply_search_filter(self) -> None:
        self.load_products()

    def load_products(self) -> None:
        keyword = self.search_input.text().strip()
        self.total_products = db.count_products(keyword)
        if self.total_products == 0:
            self.current_offset = 0
        elif self.current_offset >= self.total_products:
            self.current_offset = ((self.total_products - 1) // self.page_size) * self.page_size

        products = db.search_products(
            keyword,
            limit=self.page_size,
            offset=self.current_offset,
        )
        self.products_model.set_currency_symbol(get_currency_symbol_from_settings(get_setting))
        self.products_model.set_products(products, self.current_offset)
        self.products_loaded = True
        self.update_print_label_button_state()
        self.update_pagination_controls()

    def update_pagination_controls(self) -> None:
        if self.total_products == 0:
            self.pagination_label.setText("No products found")
        else:
            start = self.current_offset + 1
            end = min(self.current_offset + self.products_model.rowCount(), self.total_products)
            self.pagination_label.setText(
                f"Showing {start}-{end} of {self.total_products} products"
            )
        self.previous_page_button.setEnabled(self.current_offset > 0)
        self.next_page_button.setEnabled(self.current_offset + self.page_size < self.total_products)

    def previous_page(self) -> None:
        if self.current_offset <= 0:
            return
        self.current_offset = max(0, self.current_offset - self.page_size)
        self.load_products()

    def next_page(self) -> None:
        if self.current_offset + self.page_size >= self.total_products:
            return
        self.current_offset += self.page_size
        self.load_products()

    def reload_data(self) -> None:
        self.load_products()

    def open_add_dialog(self) -> None:
        dialog = ProductDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_offset = 0
            self.load_products()
            self.data_changed.emit()

    def open_edit_dialog(self, product_id: int) -> None:
        product = db.get_product_by_id(product_id)
        if product is None:
            QMessageBox.warning(self, "Product Missing", "This product could not be found.")
            self.load_products()
            return

        dialog = ProductDialog(product=product, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_products()
            self.data_changed.emit()

    def open_print_label_dialog(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            QMessageBox.information(self, "Select Product", "Please select a product to print labels.")
            return

        product = db.get_product_by_id(product_id)
        if product is None:
            QMessageBox.warning(self, "Product Missing", "This product could not be found.")
            self.load_products()
            return

        dialog = ProductLabelPrintDialog(
            product=product,
            currency_symbol=get_currency_symbol_from_settings(get_setting),
            parent=self,
        )
        dialog.exec()
        if dialog.product_updated:
            self.load_products()
            self.data_changed.emit()

    def selected_product_id(self) -> int | None:
        selection_model = self.products_table.selectionModel()
        if selection_model is None:
            return None

        selected_rows = selection_model.selectedRows()
        if selected_rows:
            return self.products_model.product_id_at(selected_rows[0].row())

        current_index = self.products_table.currentIndex()
        if current_index.isValid():
            return self.products_model.product_id_at(current_index.row())
        return None

    def update_print_label_button_state(self, *_args) -> None:
        self.print_label_button.setEnabled(self.selected_product_id() is not None)

    def delete_product(self, product_id: int) -> None:
        if not confirm_delete(
            self,
            "Are you sure you want to delete this product?",
        ):
            return

        def delete_task() -> None:
            db.delete_product_cloud_required(product_id)

        def on_success(_result) -> None:
            self.load_products()
            self.data_changed.emit()

        def on_error(error: Exception) -> None:
            QMessageBox.warning(self, "Delete Sync Error", friendly_error(error))
            self.load_products()

        self.blocking_task_runner.start(
            task=delete_task,
            message="Deleting product from cloud...",
            on_success=on_success,
            on_error=on_error,
            timeout_ms=PRODUCT_SYNC_TIMEOUT_MS,
            timeout_message="Product delete sync is taking too long. Please try again.",
        )

    def retry_product_sync(self, product_id: int) -> None:
        def retry_task() -> bool:
            return db.retry_product_sync_required(product_id)

        def on_success(_result) -> None:
            self.load_products()
            self.data_changed.emit()

        def on_error(error: Exception) -> None:
            QMessageBox.warning(self, "Product Sync Error", friendly_error(error))
            self.load_products()

        self.blocking_task_runner.start(
            task=retry_task,
            message="Retrying product sync...",
            on_success=on_success,
            on_error=on_error,
            timeout_ms=PRODUCT_SYNC_TIMEOUT_MS,
            timeout_message="Product sync is taking too long. Please try again.",
        )

    def format_barcodes_for_table(self, barcodes: list[str]) -> str:
        return format_barcodes_for_display(barcodes)

    def showEvent(self, event) -> None:
        super().showEvent(event)

    def apply_styles(self) -> None:
        self.setStyleSheet(build_product_management_stylesheet())
