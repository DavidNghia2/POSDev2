import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
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

from database import db


class ProductManagementWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_product_id: int | None = None

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
        self.search_input.setPlaceholderText("Search by Name or Barcode...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_products)
        root_layout.addWidget(self.search_input)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        root_layout.addLayout(content_layout, 1)

        form_panel = self.create_form_panel()
        table_panel = self.create_table_panel()

        content_layout.addWidget(form_panel)
        content_layout.addWidget(table_panel, 1)

    def create_form_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(360)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        section_label = QLabel("Product Details")
        section_label.setObjectName("sectionLabel")
        layout.addWidget(section_label)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form_layout)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Barcode")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product Name")

        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Price")
        self.price_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2))

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Category")

        self.requires_weight_checkbox = QCheckBox("Requires Weight")

        form_layout.addRow("Barcode", self.barcode_input)
        form_layout.addRow("Product Name", self.name_input)
        form_layout.addRow("Price", self.price_input)
        form_layout.addRow("Category", self.category_input)
        form_layout.addRow("", self.requires_weight_checkbox)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        layout.addLayout(button_layout)

        self.add_button = QPushButton("Add Product")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_product)

        self.update_button = QPushButton("Update Product")
        self.update_button.setObjectName("secondaryButton")
        self.update_button.clicked.connect(self.update_product)

        self.delete_button = QPushButton("Delete Product")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_product)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        layout.addStretch()

        return panel

    def create_table_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(640)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        section_label = QLabel("Products")
        section_label.setObjectName("sectionLabel")
        layout.addWidget(section_label)

        self.products_table = QTableWidget()
        self.products_table.setColumnCount(6)
        self.products_table.setHorizontalHeaderLabels(
            ["No.", "Barcode", "Product Name", "Price", "Category", "Requires Weight"]
        )
        self.products_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.products_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.products_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setShowGrid(False)
        self.products_table.setWordWrap(False)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.products_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self.products_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.products_table.setColumnWidth(1, 160)
        self.products_table.setColumnWidth(4, 150)
        self.products_table.itemSelectionChanged.connect(self.load_selected_product)

        layout.addWidget(self.products_table, 1)
        return panel

    def load_products(self) -> None:
        keyword = self.search_input.text().strip()
        products = db.search_products(keyword) if keyword else db.get_all_products()

        self.products_table.setRowCount(len(products))
        for row_index, product in enumerate(products):
            values = [
                str(row_index + 1),
                product["barcode"] or "",
                product["name"] or "",
                f'{float(product["price"]):.2f}',
                product["category"] or "",
                "Yes" if product["requires_weight"] else "No",
            ]

            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column_index == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, int(product["id"]))
                if column_index in (1, 2, 4):
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.products_table.setItem(row_index, column_index, table_item)

    def reload_data(self) -> None:
        self.load_products()

    def load_selected_product(self) -> None:
        selected_row = self.products_table.currentRow()
        if selected_row < 0:
            return

        self.selected_product_id = int(
            self.products_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        )
        self.barcode_input.setText(self.products_table.item(selected_row, 1).text())
        self.name_input.setText(self.products_table.item(selected_row, 2).text())
        self.price_input.setText(self.products_table.item(selected_row, 3).text())
        self.category_input.setText(self.products_table.item(selected_row, 4).text())
        self.requires_weight_checkbox.setChecked(
            self.products_table.item(selected_row, 5).text() == "Yes"
        )

    def add_product(self) -> None:
        form_data = self.get_form_data()
        if form_data is None:
            return

        try:
            db.add_product(*form_data)
        except sqlite3.IntegrityError:
            self.show_error("A product with this barcode already exists.")
            return

        self.clear_form()
        self.load_products()
        self.data_changed.emit()

    def update_product(self) -> None:
        if self.selected_product_id is None:
            self.show_error("Please select a product to update.")
            return

        form_data = self.get_form_data()
        if form_data is None:
            return

        try:
            db.update_product(self.selected_product_id, *form_data)
        except sqlite3.IntegrityError:
            self.show_error("A product with this barcode already exists.")
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

    def get_form_data(self) -> tuple[str, str, float, str, bool] | None:
        barcode = self.barcode_input.text().strip()
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

        return barcode, name, price, category, requires_weight

    def clear_form(self) -> None:
        self.selected_product_id = None
        was_blocked = self.products_table.blockSignals(True)
        self.products_table.clearSelection()
        self.products_table.setCurrentCell(-1, -1)
        self.products_table.blockSignals(was_blocked)

        self.barcode_input.clear()
        self.name_input.clear()
        self.price_input.clear()
        self.category_input.clear()
        self.requires_weight_checkbox.setChecked(False)
        self.barcode_input.setFocus()

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

            #panel {
                background: #FFFFFF;
                border: 1px solid #D8E0E8;
                border-radius: 10px;
            }

            QLabel {
                background: transparent;
            }

            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #C9D3DE;
                border-radius: 8px;
                padding: 10px 12px;
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
