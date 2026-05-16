"""Helpers for showing payment QR images clearly without modifying originals."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QPixmap


def _center_square_rect(width: int, height: int) -> QRect:
    side = min(width, height)
    x = max((width - side) // 2, 0)
    y = max((height - side) // 2, 0)
    return QRect(x, y, side, side)


def center_square_crop(source: QPixmap) -> QPixmap:
    """Return a centered square crop so poster-like QR images do not appear tiny."""
    rect = _center_square_rect(source.width(), source.height())
    if rect.width() <= 0:
        return source
    return source.copy(rect)


def _is_dark_pixel(pixel: int) -> bool:
    red = (pixel >> 16) & 0xFF
    green = (pixel >> 8) & 0xFF
    blue = pixel & 0xFF
    luminance = (red * 299 + green * 587 + blue * 114) // 1000
    return luminance < 115 and max(red, green, blue) < 170


def _merged_segments(active_indexes: list[int], max_gap: int) -> list[tuple[int, int]]:
    if not active_indexes:
        return []

    segments: list[tuple[int, int]] = []
    start = active_indexes[0]
    previous = active_indexes[0]

    for index in active_indexes[1:]:
        if index - previous > max_gap:
            segments.append((start, previous))
            start = index
        previous = index

    segments.append((start, previous))
    return segments


def _best_segment(
    counts: list[int],
    active_threshold: int,
    max_gap: int,
    min_length: int,
) -> tuple[int, int] | None:
    active_indexes = [index for index, count in enumerate(counts) if count >= active_threshold]
    candidates = [
        segment
        for segment in _merged_segments(active_indexes, max_gap)
        if segment[1] - segment[0] + 1 >= min_length
    ]
    if not candidates:
        return None

    def score(segment: tuple[int, int]) -> int:
        start, end = segment
        length = end - start + 1
        return sum(counts[start : end + 1]) * length

    return max(candidates, key=score)


def _clamped_square_rect(center_x: int, center_y: int, side: int, width: int, height: int) -> QRect:
    side = max(1, min(side, width, height))
    x = center_x - side // 2
    y = center_y - side // 2
    x = max(0, min(x, width - side))
    y = max(0, min(y, height - side))
    return QRect(x, y, side, side)


def _detect_qr_rect(source: QPixmap) -> QRect | None:
    """Detect the dense QR-matrix area and return a square crop rect on the original image."""
    if source.isNull() or source.width() <= 0 or source.height() <= 0:
        return None

    max_analysis_side = 620
    analysis = source
    if max(source.width(), source.height()) > max_analysis_side:
        analysis = source.scaled(
            max_analysis_side,
            max_analysis_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    image = analysis.toImage().convertToFormat(QImage.Format.Format_RGB32)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None

    row_counts = [0 for _ in range(height)]
    row_min_x = [width for _ in range(height)]
    row_max_x = [-1 for _ in range(height)]

    for y in range(height):
        for x in range(width):
            if _is_dark_pixel(image.pixel(x, y)):
                row_counts[y] += 1
                row_min_x[y] = min(row_min_x[y], x)
                row_max_x[y] = max(row_max_x[y], x)

    row_segment = _best_segment(
        row_counts,
        active_threshold=max(4, int(width * 0.035)),
        max_gap=max(4, int(height * 0.012)),
        min_length=max(14, int(height * 0.045)),
    )
    if row_segment is None:
        return None

    y1, y2 = row_segment
    col_counts = [0 for _ in range(width)]
    for y in range(y1, y2 + 1):
        if row_max_x[y] < row_min_x[y]:
            continue
        for x in range(row_min_x[y], row_max_x[y] + 1):
            if _is_dark_pixel(image.pixel(x, y)):
                col_counts[x] += 1

    segment_height = y2 - y1 + 1
    col_segment = _best_segment(
        col_counts,
        active_threshold=max(3, int(segment_height * 0.035)),
        max_gap=max(4, int(width * 0.012)),
        min_length=max(14, int(width * 0.045)),
    )
    if col_segment is None:
        return None

    x1, x2 = col_segment
    qr_width = x2 - x1 + 1
    qr_height = y2 - y1 + 1
    qr_side = max(qr_width, qr_height)

    # Include the white quiet zone around the QR, but avoid pulling in poster text below it.
    padded_side = int(qr_side * 1.16)
    crop_rect = _clamped_square_rect(
        center_x=(x1 + x2) // 2,
        center_y=(y1 + y2) // 2,
        side=padded_side,
        width=width,
        height=height,
    )

    scale_x = source.width() / width
    scale_y = source.height() / height
    original_rect = QRect(
        int(crop_rect.x() * scale_x),
        int(crop_rect.y() * scale_y),
        max(1, int(crop_rect.width() * scale_x)),
        max(1, int(crop_rect.height() * scale_y)),
    )
    return original_rect.intersected(QRect(0, 0, source.width(), source.height()))


def qr_focus_crop(source: QPixmap) -> QPixmap:
    """Crop to the QR code itself when possible; fall back to a centered square."""
    detected_rect = _detect_qr_rect(source)
    if detected_rect is None or detected_rect.width() <= 0:
        return center_square_crop(source)
    return source.copy(detected_rect)


def qr_focus_pixmap(image_path: str | Path, size: int = 260) -> QPixmap:
    """Load an image, crop to the QR area, then scale it for display."""
    pixmap = QPixmap(str(image_path))
    if pixmap.isNull():
        return pixmap

    focused_pixmap = qr_focus_crop(pixmap)
    return focused_pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
