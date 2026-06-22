from __future__ import annotations

from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter
from PyQt6.QtPrintSupport import QPrinter


LABEL_MODE_BARCODE = "barcode"
LABEL_MODE_PRICE = "price"

STICKER_SIZES: dict[str, dict[str, object]] = {
    "small": {
        "label": "Small",
        "width_mm": 50.0,
        "height_mm": 25.0,
        "description": "Compact sticker for small products",
    },
    "medium": {
        "label": "Medium",
        "width_mm": 70.0,
        "height_mm": 35.0,
        "description": "Standard product sticker",
    },
    "large": {
        "label": "Large",
        "width_mm": 100.0,
        "height_mm": 50.0,
        "description": "Large shelf or product sticker",
    },
    "tag": {
        "label": "Tag",
        "width_mm": 60.0,
        "height_mm": 40.0,
        "description": "Hanging product tag",
    },
}
DEFAULT_STICKER_SIZE = "medium"

# Code 128 symbol widths for values 0-106. Each digit is a module width,
# alternating black and white bars from left to right.
CODE128_PATTERNS = [
    "212222",
    "222122",
    "222221",
    "121223",
    "121322",
    "131222",
    "122213",
    "122312",
    "132212",
    "221213",
    "221312",
    "231212",
    "112232",
    "122132",
    "122231",
    "113222",
    "123122",
    "123221",
    "223211",
    "221132",
    "221231",
    "213212",
    "223112",
    "312131",
    "311222",
    "321122",
    "321221",
    "312212",
    "322112",
    "322211",
    "212123",
    "212321",
    "232121",
    "111323",
    "131123",
    "131321",
    "112313",
    "132113",
    "132311",
    "211313",
    "231113",
    "231311",
    "112133",
    "112331",
    "132131",
    "113123",
    "113321",
    "133121",
    "313121",
    "211331",
    "231131",
    "213113",
    "213311",
    "213131",
    "311123",
    "311321",
    "331121",
    "312113",
    "312311",
    "332111",
    "314111",
    "221411",
    "431111",
    "111224",
    "111422",
    "121124",
    "121421",
    "141122",
    "141221",
    "112214",
    "112412",
    "122114",
    "122411",
    "142112",
    "142211",
    "241211",
    "221114",
    "413111",
    "241112",
    "134111",
    "111242",
    "121142",
    "121241",
    "114212",
    "124112",
    "124211",
    "411212",
    "421112",
    "421211",
    "212141",
    "214121",
    "412121",
    "111143",
    "111341",
    "131141",
    "114113",
    "114311",
    "411113",
    "411311",
    "113141",
    "114131",
    "311141",
    "411131",
    "211412",
    "211214",
    "211232",
    "2331112",
]


def get_sticker_size(size_key: str | None) -> dict[str, object]:
    return STICKER_SIZES.get(size_key or "", STICKER_SIZES[DEFAULT_STICKER_SIZE])


def sticker_size_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for key, info in STICKER_SIZES.items():
        width = _format_mm(float(info["width_mm"]))
        height = _format_mm(float(info["height_mm"]))
        options.append((key, f'{info["label"]} ({width}x{height} mm)'))
    return options


def configure_sticker_printer(printer: QPrinter, size_key: str, doc_name: str) -> None:
    size = get_sticker_size(size_key)
    width_mm = float(size["width_mm"])
    height_mm = float(size["height_mm"])
    label = str(size["label"])

    printer.setDocName(doc_name)
    printer.setFullPage(True)
    printer.setPageSize(QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter, label))
    printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)


def can_encode_code128(value: str) -> bool:
    return bool(value) and all(32 <= ord(character) <= 126 for character in value)


def render_product_labels(
    printer: QPrinter,
    mode: str,
    product_name: str,
    price_text: str,
    barcode: str,
    size_key: str,
    quantity: int,
) -> None:
    configure_sticker_printer(printer, size_key, "Product Label")
    painter = QPainter()
    if not painter.begin(printer):
        return

    try:
        copies = max(1, int(quantity))
        for copy_index in range(copies):
            if copy_index > 0:
                printer.newPage()
            _render_single_label(
                painter,
                printer.pageRect(QPrinter.Unit.DevicePixel),
                mode,
                product_name,
                price_text,
                barcode,
                size_key,
            )
    finally:
        painter.end()


def _render_single_label(
    painter: QPainter,
    page_rect: QRectF,
    mode: str,
    product_name: str,
    price_text: str,
    barcode: str,
    size_key: str,
) -> None:
    size = get_sticker_size(size_key)
    width_mm = float(size["width_mm"])
    height_mm = float(size["height_mm"])
    label_context = _LabelContext(page_rect, width_mm, height_mm)

    painter.save()
    painter.fillRect(page_rect, QColor("#FFFFFF"))
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if mode == LABEL_MODE_PRICE:
        _draw_price_label(painter, label_context, product_name, price_text)
    else:
        _draw_barcode_label(painter, label_context, barcode)

    painter.restore()


def _draw_barcode_label(painter: QPainter, context: "_LabelContext", barcode: str) -> None:
    margin_x = 3.0 if context.width_mm <= 50 else 4.0
    margin_y = 2.4 if context.height_mm <= 25 else 3.2
    text_height = 4.8 if context.height_mm <= 25 else 6.5
    gap = 1.2 if context.height_mm <= 25 else 1.8

    barcode_rect = context.rect_mm(
        margin_x,
        margin_y,
        context.width_mm - (margin_x * 2),
        max(8.0, context.height_mm - (margin_y * 2) - text_height - gap),
    )
    text_rect = context.rect_mm(
        margin_x,
        context.height_mm - margin_y - text_height,
        context.width_mm - (margin_x * 2),
        text_height,
    )

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    _draw_code128_bars(painter, barcode_rect, barcode)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _draw_fitted_text(
        painter,
        text_rect,
        barcode,
        min_point=6,
        max_point=11 if context.width_mm <= 50 else 13,
        weight=QFont.Weight.DemiBold,
        flags=Qt.AlignmentFlag.AlignCenter,
    )


def _draw_price_label(
    painter: QPainter,
    context: "_LabelContext",
    product_name: str,
    price_text: str,
) -> None:
    margin_x = 3.6 if context.width_mm <= 50 else 5.0
    margin_y = 2.8 if context.height_mm <= 25 else 4.2
    content_width = context.width_mm - (margin_x * 2)
    content_height = context.height_mm - (margin_y * 2)
    name_height = max(7.0, content_height * 0.46)
    price_top = margin_y + name_height + 1.4
    price_height = max(7.0, context.height_mm - price_top - margin_y)

    name_rect = context.rect_mm(margin_x, margin_y, content_width, name_height)
    price_rect = context.rect_mm(margin_x, price_top, content_width, price_height)

    _draw_fitted_text(
        painter,
        name_rect,
        product_name.strip() or "Product",
        min_point=7,
        max_point=18 if context.width_mm >= 70 else 14,
        weight=QFont.Weight.DemiBold,
        flags=Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignVCenter
        | Qt.TextFlag.TextWordWrap,
    )
    _draw_fitted_text(
        painter,
        price_rect,
        price_text,
        min_point=9,
        max_point=30 if context.width_mm >= 70 else 21,
        weight=QFont.Weight.Black,
        flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )


def _draw_code128_bars(painter: QPainter, rect: QRectF, value: str) -> None:
    encoded_values = _encode_code128_b(value)
    total_modules = sum(sum(int(width) for width in CODE128_PATTERNS[code]) for code in encoded_values)
    module_width = rect.width() / total_modules

    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#111827"))
    x = rect.left()
    for code in encoded_values:
        draw_bar = True
        for width_text in CODE128_PATTERNS[code]:
            width = int(width_text) * module_width
            if draw_bar:
                painter.drawRect(QRectF(x, rect.top(), width, rect.height()))
            x += width
            draw_bar = not draw_bar
    painter.restore()


def _encode_code128_b(value: str) -> list[int]:
    if not can_encode_code128(value):
        raise ValueError("Barcode can only contain printable ASCII characters.")

    start_code_b = 104
    data_codes = [ord(character) - 32 for character in value]
    checksum = start_code_b
    for index, code in enumerate(data_codes, start=1):
        checksum += code * index
    checksum %= 103
    return [start_code_b, *data_codes, checksum, 106]


def _draw_fitted_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    min_point: int,
    max_point: int,
    weight: QFont.Weight,
    flags: Qt.AlignmentFlag | Qt.TextFlag,
) -> None:
    font = _fit_font(painter, rect, text, min_point, max_point, weight, int(flags))
    painter.save()
    painter.setPen(QColor("#111827"))
    painter.setFont(font)
    painter.drawText(rect, int(flags), text)
    painter.restore()


def _fit_font(
    painter: QPainter,
    rect: QRectF,
    text: str,
    min_point: int,
    max_point: int,
    weight: QFont.Weight,
    flags: int,
) -> QFont:
    font = QFont("Segoe UI")
    font.setWeight(weight)
    for point_size in range(max_point, min_point - 1, -1):
        font.setPointSize(point_size)
        metrics = QFontMetricsF(font, painter.device())
        bounds = metrics.boundingRect(rect, flags, text)
        if bounds.width() <= rect.width() and bounds.height() <= rect.height():
            return QFont(font)
    font.setPointSize(min_point)
    return font


def _format_mm(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


class _LabelContext:
    def __init__(self, page_rect: QRectF, width_mm: float, height_mm: float) -> None:
        self.page_rect = page_rect
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.scale_x = page_rect.width() / width_mm
        self.scale_y = page_rect.height() / height_mm

    def rect_mm(self, left: float, top: float, width: float, height: float) -> QRectF:
        return QRectF(
            self.page_rect.left() + (left * self.scale_x),
            self.page_rect.top() + (top * self.scale_y),
            width * self.scale_x,
            height * self.scale_y,
        )
