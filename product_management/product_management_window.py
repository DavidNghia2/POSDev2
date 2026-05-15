import sqlite3
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import db


class ProductManagementWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_product_id: int | None = None
        self.image_path = ""
        self.barcodes: list[str] = []

        db.init_db()
        self.create_ui()
        self.apply_styles()
        self.load_products()

    def create_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 28)
        root_layout.setSpacing(18)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(4)

        title_label = QLabel("Product Management")
        title_label.setObjectName("titleLabel")

        subtitle_label = QLabel("Manage product catalog, prices, categories, and weighted items")
        subtitle_label.setObjectName("subtitleLabel")

        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)

        header_layout.addLayout(title_block)
        header_layout.addStretch()
        root_layout.addLayout(header_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Product Name or any Barcode...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_products)
        root_layout.addWidget(self.search_input)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        root_layout.addLayout(content_layout, 1)

        content_layout.addWidget(self.create_form_panel())
        content_layout.addWidget(self.create_table_panel(), 1)

    def create_form_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(390)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        form_scroll = QScrollArea()
        form_scroll.setObjectName("formScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(form_scroll)

        form_body = QWidget()
        form_body.setObjectName("formBody")
        form_scroll.setWidget(form_body)

        layout = QVBoxLayout(form_body)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        section_label = QLabel("Product Details")
        section_label.setObjectName("sectionLabel")
        layout.addWidget(section_label)

        self.image_preview = QLabel("No Image")
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFixedHeight(145)
        layout.addWidget(self.image_preview)

        choose_image_button = QPushButton("Choose Image")
        choose_image_button.setObjectName("secondaryButton")
        choose_image_button.setMinimumHeight(42)
        choose_image_button.clicked.connect(self.choose_image)
        layout.addWidget(choose_image_button)

        barcode_section = QVBoxLayout()
        barcode_section.setContentsMargins(0, 4, 0, 0)
        barcode_section.setSpacing(8)

        barcode_label = QLabel("Barcodes")
        barcode_label.setObjectName("fieldSectionLabel")
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
        self.barcode_input.setMinimumHeight(42)
        self.barcode_input.returnPressed.connect(self.add_barcode_from_input)

        add_barcode_button = QPushButton("Add Barcode")
        add_barcode_button.setObjectName("smallButton")
        add_barcode_button.setMinimumHeight(42)
        add_barcode_button.clicked.connect(self.add_barcode_from_input)

        barcode_input_row.addWidget(self.barcode_input, 1)
        barcode_input_row.addWidget(add_barcode_button)
        barcode_section.addLayout(barcode_input_row)

        self.barcode_list_widget = QWidget()
        self.barcode_list_layout = QVBoxLayout(self.barcode_list_widget)
        self.barcode_list_layout.setContentsMargins(0, 0, 0, 0)
        self.barcode_list_layout.setSpacing(6)
        self.barcode_list_layout.addStretch()

        barcode_scroll = QScrollArea()
        barcode_scroll.setObjectName("barcodeScroll")
        barcode_scroll.setWidgetResizable(True)
        barcode_scroll.setFrameShape(QFrame.Shape.NoFrame)
        barcode_scroll.setFixedHeight(96)
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
        self.name_input.setMinimumHeight(42)

        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Price")
        self.price_input.setMinimumHeight(42)
        self.price_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Category")
        self.category_input.setMinimumHeight(42)

        self.requires_weight_checkbox = QCheckBox()
        self.requires_weight_checkbox.setMinimumHeight(28)

        form_layout.addRow("Product Name", self.name_input)
        form_layout.addRow("Price", self.price_input)
        form_layout.addRow("Category", self.category_input)
        form_layout.addRow("Requires Weight", self.requires_weight_checkbox)

        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.setSpacing(10)
        layout.addLayout(button_layout)

        self.add_button = QPushButton("Add Product")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumHeight(42)
        self.add_button.clicked.connect(self.add_product)

        self.update_button = QPushButton("Update Product")
        self.update_button.setObjectName("secondaryButton")
        self.update_button.setMinimumHeight(42)
        self.update_button.clicked.connect(self.update_product)

        self.delete_button = QPushButton("Delete Product")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setMinimumHeight(42)
        self.delete_button.clicked.connect(self.delete_product)

        self.clear_button = QPushButton("Clear Form")
        self.clear_button.setObjectName("neutralButton")
        self.clear_button.setMinimumHeight(42)
        self.clear_button.clicked.connect(self.clear_form)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)
        layout.addStretch()

        self.render_barcode_list()
        return panel

    def create_table_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(720)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        section_label = QLabel("Products")
        section_label.setObjectName("sectionLabel")
        layout.addWidget(section_label)

        self.products_table = QTableWidget()
        self.products_table.setColumnCount(7)
        self.products_table.setHorizontalHeaderLabels(
            ["No", "Image", "Product Name", "Barcodes", "Price", "Category", "Requires Weight"]
        )
        self.products_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.products_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.products_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setShowGrid(False)
        self.products_table.setWordWrap(False)
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
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.products_table.setColumnWidth(1, 82)
        self.products_table.setColumnWidth(3, 220)
        self.products_table.itemSelectionChanged.connect(self.load_selected_product)

        layout.addWidget(self.products_table, 1)
        return panel

    def load_products(self) -> None:
        keyword = self.search_input.text().strip()
        products = db.search_products(keyword) if keyword else db.get_all_products()

        self.products_table.setRowCount(len(products))
        for row_index, product in enumerate(products):
            barcodes = list(product.get("barcodes") or [])
            values = [
                str(row_index + 1),
                "",
                product["name"] or "",
                self.format_barcodes_for_table(barcodes),
                f'{float(product["price"]):.2f}',
                product["category"] or "",
                "Yes" if product["requires_weight"] else "No",
            ]

            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column_index == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, int(product["id"]))
                if column_index in (2, 3, 5):
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.products_table.setItem(row_index, column_index, table_item)

            self.products_table.setCellWidget(
                row_index,
                1,
                self.create_table_image_label(str(product.get("image_path") or "")),
            )

    def reload_data(self) -> None:
        self.load_products()

    def load_selected_product(self) -> None:
        selected_row = self.products_table.currentRow()
        if selected_row < 0:
            return

        product_id = int(self.products_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole))
        product = db.get_product_by_id(product_id)
        if product is None:
            return

        self.selected_product_id = product_id
        self.image_path = str(product.get("image_path") or "")
        self.barcodes = list(product.get("barcodes") or [])
        self.name_input.setText(str(product.get("name") or ""))
        self.price_input.setText(f'{float(product["price"]):.2f}')
        self.category_input.setText(str(product.get("category") or ""))
        self.requires_weight_checkbox.setChecked(bool(product.get("requires_weight")))
        self.barcode_input.clear()
        self.update_image_preview()
        self.render_barcode_list()

    def add_product(self) -> None:
        form_data = self.get_form_data(include_pending_barcode=True)
        if form_data is None:
            return

        try:
            db.add_product(*form_data)
        except sqlite3.IntegrityError:
            self.show_error("A product with one of these barcodes already exists.")
            return

        self.clear_form()
        self.load_products()
        self.data_changed.emit()

    def update_product(self) -> None:
        if self.selected_product_id is None:
            self.show_error("Please select a product to update.")
            return

        form_data = self.get_form_data(include_pending_barcode=True)
        if form_data is None:
            return

        try:
            db.update_product(self.selected_product_id, *form_data)
        except sqlite3.IntegrityError:
            self.show_error("A product with one of these barcodes already exists.")
            return

        self.clear_form()
        self.load_products()
        self.data_changed.emit()

    def delete_product(self) -> None:
        if self.selected_product_id is None:
            self.show_error("Please select a product to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this product?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        db.delete_product(self.selected_product_id)
        self.clear_form()
        self.load_products()
        self.data_changed.emit()

    def get_form_data(
        self,
        include_pending_barcode: bool = False,
    ) -> tuple[str, float, str, bool, str, list[str]] | None:
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

        return name, price, category, requires_weight, self.image_path, barcodes

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
        if not self.add_barcode(self.barcode_input.text().strip()):
            return
        if self.selected_product_id is not None:
            self.save_selected_product_changes(clear_form_after_save=False)

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
        if db.barcode_exists(clean_barcode, self.selected_product_id):
            self.show_error("This barcode is already assigned to another product.")
            return False
        return True

    def remove_barcode(self, barcode: str) -> None:
        previous_barcodes = list(self.barcodes)
        self.barcodes = [item for item in self.barcodes if item != barcode]
        self.render_barcode_list()
        if self.selected_product_id is not None and not self.save_selected_product_changes(
            clear_form_after_save=False
        ):
            self.barcodes = previous_barcodes
            self.render_barcode_list()

    def save_selected_product_changes(self, clear_form_after_save: bool) -> bool:
        if self.selected_product_id is None:
            return False

        form_data = self.get_form_data(include_pending_barcode=False)
        if form_data is None:
            return False

        try:
            db.update_product(self.selected_product_id, *form_data)
        except sqlite3.IntegrityError:
            self.show_error("A product with one of these barcodes already exists.")
            return False

        saved_product_id = self.selected_product_id
        if clear_form_after_save:
            self.clear_form()
        else:
            self.load_products()
            self.select_product_in_table(saved_product_id)
        self.data_changed.emit()
        self.show_status("Barcode list saved to selected product.")
        return True

    def select_product_in_table(self, product_id: int) -> None:
        for row in range(self.products_table.rowCount()):
            item = self.products_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == product_id:
                self.products_table.setCurrentCell(row, 0)
                self.products_table.selectRow(row)
                return

    def show_status(self, message: str) -> None:
        status_bar = getattr(self.window(), "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(message, 2500)

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

        delete_button = QPushButton("X")
        delete_button.setObjectName("barcodeDeleteButton")
        delete_button.setToolTip("Remove barcode")
        delete_button.setFixedSize(26, 24)
        delete_button.clicked.connect(lambda _checked=False, value=barcode: self.remove_barcode(value))

        row_layout.addWidget(label, 1)
        row_layout.addWidget(variant_label)
        row_layout.addWidget(delete_button)
        return row

    def update_image_preview(self) -> None:
        self.set_label_pixmap(self.image_preview, self.image_path, "No Image", 330, 140)

    def create_table_image_label(self, image_path: str) -> QLabel:
        label = QLabel("No Image")
        label.setObjectName("tableImage")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(70, 54)
        self.set_label_pixmap(label, image_path, "No Image", 64, 48)
        return label

    def set_label_pixmap(
        self,
        label: QLabel,
        image_path: str,
        fallback_text: str,
        width: int,
        height: int,
    ) -> None:
        if image_path and Path(image_path).exists():
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        width,
                        height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                label.setText("")
                return
        label.setPixmap(QPixmap())
        label.setText(fallback_text)

    def format_barcodes_for_table(self, barcodes: list[str]) -> str:
        if not barcodes:
            return ""
        if len(barcodes) <= 3:
            return ", ".join(barcodes)
        return f"{barcodes[0]} + {len(barcodes) - 1} more"

    def clear_form(self) -> None:
        self.selected_product_id = None
        was_blocked = self.products_table.blockSignals(True)
        self.products_table.clearSelection()
        self.products_table.setCurrentCell(-1, -1)
        self.products_table.blockSignals(was_blocked)

        self.image_path = ""
        self.barcodes = []
        self.barcode_input.clear()
        self.name_input.clear()
        self.price_input.clear()
        self.category_input.clear()
        self.requires_weight_checkbox.setChecked(False)
        self.update_image_preview()
        self.render_barcode_list()
        self.name_input.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.load_products()

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Validation Error", message)

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

            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
            }

            #formScroll, #formBody {
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

            QTableWidget::item {
                border-bottom: 1px solid #EDF1F5;
                padding: 8px;
            }
            """
        )
