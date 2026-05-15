"""Application branding assets and helpers."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget


APP_NAME = "Retail POS"
APP_LOGO_RELATIVE_PATH = Path("assets") / "app_logo.png"


def app_logo_path() -> Path:
    """Return the app logo path in development or a frozen bundle."""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base_dir / APP_LOGO_RELATIVE_PATH


def app_icon() -> QIcon:
    return QIcon(str(app_logo_path()))


def app_logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(str(app_logo_path()))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def apply_app_icon(window: QWidget | None = None) -> QIcon:
    """Apply the app icon globally and, optionally, to a specific window."""
    icon = app_icon()
    if icon.isNull():
        return icon

    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(icon)

    if window is not None:
        window.setWindowIcon(icon)

    return icon
