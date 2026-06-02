import sqlite3
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QDoubleValidator, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from database import db
from login import get_setting
from ui.currency import DEFAULT_CURRENCY_SYMBOL, format_money, get_currency_symbol_from_settings
from ui.dialogs import confirm_delete
from ui.icon_manager import IconManager
from ui.loading import BlockingTaskRunner, PRODUCT_SYNC_TIMEOUT_MS
from ui.theme import MODERN_WIDGET_STYLESHEET
from ui.thumbnail_cache import ThumbnailCache

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_TABLE_PAGE_SIZE = 250

PRODUCT_MANAGEMENT_STYLESHEET = """
QWidget {
    background: #EEF1F4;
    color: #1F2933;
    font-family: "Segoe UI";
    font-size: 13px;
}

QDialog {
    background: #EEF1F4;
}

#titleLabel {
    color: #17212B;
    font-size: 26px;
    font-weight: 700;
}

#dialogTitleLabel {
    color: #17212B;
    font-size: 22px;
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

#fieldSectionLabel {
    color: #25313D;
    font-size: 13px;
    font-weight: 700;
}

#barcodeRules {
    background: #F0F7FF;
    border: 1px solid #CFE3FF;
    border-radius: 8px;
    color: #32506D;
    font-size: 11px;
    font-weight: 600;
    padding: 8px 10px;
}

#panel, #dialogPanel {
    background: #FFFFFF;
    border: 1px solid #D8E0E8;
    border-radius: 10px;
}

#dialogScroll, #dialogBody {
    background: #FFFFFF;
    border: none;
}

QLabel {
    background: transparent;
}

#imagePreview, #tableImage {
    background: #F8FAFC;
    border: 1px solid #D8E0E8;
    border-radius: 8px;
    color: #64707D;
    font-size: 12px;
    font-weight: 700;
}

#barcodeScroll {
    background: #F8FAFC;
    border: 1px solid #D8E0E8;
    border-radius: 8px;
}

#barcodeRow {
    background: #FFFFFF;
    border: 1px solid #E5EAF0;
    border-radius: 7px;
}

#barcodeValue {
    color: #25313D;
    font-weight: 700;
}

#barcodeVariant {
    background: #EAF4FE;
    border: 1px solid #CFE3FF;
    border-radius: 6px;
    color: #2563EB;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 7px;
}

#emptyBarcodeLabel {
    color: #7B8794;
    padding: 20px;
}

QLineEdit {
    background: #FFFFFF;
    border: 1px solid #C9D3DE;
    border-radius: 8px;
    padding: 10px 12px;
    min-height: 20px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QLineEdit:focus {
    border: 1px solid #2563EB;
}

QCheckBox {
    background: transparent;
    spacing: 8px;
    font-weight: 600;
}

QPushButton {
    border: none;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 700;
    min-height: 42px;
    padding: 0 14px;
}

#primaryButton, #rowEditButton {
    background: #2563EB;
}

#secondaryButton {
    background: #0F766E;
}

#dangerButton, #rowDeleteButton {
    background: #DC2626;
}

#neutralButton {
    background: #64748B;
}

#smallButton {
    background: #2563EB;
    min-width: 104px;
    padding: 0 12px;
}

#barcodeDeleteButton {
    background: #FEE2E2;
    color: #B91C1C;
    border-radius: 6px;
    padding: 0;
}

#rowEditButton, #rowDeleteButton {
    min-height: 32px;
    padding: 0 10px;
}

QPushButton:pressed {
    padding-top: 13px;
    padding-bottom: 11px;
}

QTableView {
    background: #FFFFFF;
    border: 1px solid #D8E0E8;
    border-radius: 8px;
    alternate-background-color: #F7F9FB;
    gridline-color: transparent;
    selection-background-color: #DBEAFE;
    selection-color: #17212B;
}

QHeaderView::section {
    background: #F0F4F8;
    border: none;
    border-bottom: 1px solid #D8E0E8;
    color: #25313D;
    font-weight: 700;
    padding: 10px;
}

QTableView::item {
    border-bottom: 1px solid #EDF1F5;
    padding: 8px;
}
""" + MODERN_WIDGET_STYLESHEET


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

        if role == Qt.ItemDataRole.ToolTipRole and column == 8:
            return str(product.get("sync_error") or product.get("sync_status") or "")

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
                return QSize(245, 54)

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
            painter.fillRect(option.rect, QColor("#DBEAFE"))

        model = index.model()
        edit_rect, retry_rect, delete_rect = self.action_rects(option.rect)
        sync_status, sync_error = model.product_sync_status_at(index.row())
        self.draw_action_button(painter, edit_rect, "Edit", "#2563EB")
        retry_color = "#F59E0B" if sync_status == "pending" or sync_error else "#94A3B8"
        self.draw_action_button(painter, retry_rect, "Retry", retry_color)
        self.draw_action_button(painter, delete_rect, "Delete", "#DC2626")

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
        button_height = 32
        edit_width = 68
        retry_width = 70
        delete_width = 78
        gap = 8
        total_width = edit_width + gap + retry_width + gap + delete_width
        left = cell_rect.left() + max((cell_rect.width() - total_width) // 2, 6)
        top = cell_rect.top() + max((cell_rect.height() - button_height) // 2, 4)
        edit_rect = QRect(left, top, edit_width, button_height)
        retry_rect = QRect(left + edit_width + gap, top, retry_width, button_height)
        delete_rect = QRect(left + edit_width + gap + retry_width + gap, top, delete_width, button_height)
        return edit_rect, retry_rect, delete_rect

    def draw_action_button(self, painter: QPainter, rect: QRect, text: str, color: str) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


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
        self.setStyleSheet(PRODUCT_MANAGEMENT_STYLESHEET)

        self.create_ui()
        if product is not None:
            self.populate_form(product)
        self.render_barcode_list()

    def create_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
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
        layout.setContentsMargins(22, 22, 22, 22)
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
        barcode_scroll.setFixedHeight(104)
        barcode_scroll.setWidget(self.barcode_list_widget)
        barcode_section.addWidget(barcode_scroll)
        layout.addLayout(barcode_section)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(10)
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
            self.show_error(f"Could not sync product to Supabase.\n\n{error}")

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
        root_layout.setSpacing(18)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Product Name or any Barcode...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.schedule_search)

        add_button = QPushButton("Add Product")
        add_button.setObjectName("primaryButton")
        IconManager.apply_button(add_button, "add", IconManager.LIGHT)
        add_button.clicked.connect(self.open_add_dialog)

        toolbar_layout.addWidget(self.search_input, 1)
        toolbar_layout.addWidget(add_button)
        root_layout.addLayout(toolbar_layout)
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
        self.products_table.verticalHeader().setDefaultSectionSize(64)
        self.products_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.products_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        self.products_table.setColumnWidth(1, 82)
        self.products_table.setColumnWidth(3, 220)
        self.products_table.setColumnWidth(8, 120)
        self.products_table.setColumnWidth(9, 245)

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
            QMessageBox.warning(self, "Delete Sync Error", f"Could not delete product in Supabase.\n\n{error}")
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
            QMessageBox.warning(self, "Product Sync Error", f"Could not sync product to Supabase.\n\n{error}")
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
        self.setStyleSheet(PRODUCT_MANAGEMENT_STYLESHEET)
