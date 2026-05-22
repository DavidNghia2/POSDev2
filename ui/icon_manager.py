"""Centralized minimalist icon system for the application UI."""

from __future__ import annotations

from typing import Final

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class IconTextLabel(QWidget):
    """Compact icon + text label used for page and section headings."""

    def __init__(
        self,
        text: str,
        icon: QIcon,
        object_name: str | None = None,
        icon_size: int = 18,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(icon_size, icon_size))
        icon_label.setFixedSize(icon_size, icon_size)

        text_label = QLabel(text)
        if object_name:
            text_label.setObjectName(object_name)

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch(1)

        self.icon_label = icon_label
        self.text_label = text_label


class IconManager:
    """Creates consistent monochrome line-art icons from one central mapping."""

    DARK: Final[str] = "#334155"
    LIGHT: Final[str] = "#FFFFFF"
    MUTED: Final[str] = "#64748B"

    _ICON_NAMES: Final[dict[str, str]] = {
        "dashboard": "mdi6.view-dashboard-outline",
        "terminal": "mdi6.cash-register",
        "products": "mdi6.package-variant-closed",
        "reports": "mdi6.file-chart-outline",
        "registers": "mdi6.archive-outline",
        "audit_logs": "mdi6.history",
        "settings": "mdi6.cog-outline",
        "users": "mdi6.account-group-outline",
        "store": "mdi6.storefront-outline",
        "payment": "mdi6.credit-card-outline",
        "cash": "mdi6.cash",
        "sales": "mdi6.chart-line",
        "items": "mdi6.package-variant-closed",
        "average": "mdi6.chart-timeline-variant-shimmer",
        "add": "mdi6.plus",
        "edit": "mdi6.pencil-outline",
        "delete": "mdi6.trash-can-outline",
        "clear": "mdi6.close",
        "save": "mdi6.content-save-outline",
        "refresh": "mdi6.refresh",
        "search": "mdi6.magnify",
        "filter": "mdi6.filter-outline",
        "calendar": "mdi6.calendar-outline",
        "upload": "mdi6.upload-outline",
        "image": "mdi6.image-outline",
        "barcode": "mdi6.barcode",
        "cart": "mdi6.cart-outline",
        "print": "mdi6.printer-outline",
        "confirm": "mdi6.check-circle-outline",
        "cancel": "mdi6.close-circle-outline",
        "close": "mdi6.close",
        "user": "mdi6.account-outline",
        "lock": "mdi6.lock-outline",
        "role": "mdi6.shield-account-outline",
        "eye": "mdi6.eye-outline",
        "eye_off": "mdi6.eye-off-outline",
        "login": "mdi6.login",
        "logout": "mdi6.logout",
        "info": "mdi6.information-outline",
        "receipt": "mdi6.receipt-text-outline",
        "discount": "mdi6.tag-outline",
        "change": "mdi6.swap-horizontal",
        "note": "mdi6.note-text-outline",
        "today": "mdi6.calendar-today",
        "week": "mdi6.calendar-week-outline",
        "month": "mdi6.calendar-month-outline",
        "sidebar_collapse": "mdi6.chevron-left",
        "sidebar_expand": "mdi6.chevron-right",
    }

    _icon_cache: dict[tuple[str, str], QIcon] = {}

    @classmethod
    def icon(cls, key: str, color: str | None = None) -> QIcon:
        icon_name = cls._ICON_NAMES[key]
        resolved_color = color or cls.DARK
        cache_key = (key, resolved_color)
        if cache_key not in cls._icon_cache:
            cls._icon_cache[cache_key] = qta.icon(icon_name, color=resolved_color)
        return cls._icon_cache[cache_key]

    @classmethod
    def pixmap(cls, key: str, size: int = 18, color: str | None = None) -> QPixmap:
        return cls.icon(key, color).pixmap(size, size)

    @classmethod
    def label(
        cls,
        text: str,
        key: str,
        object_name: str | None = None,
        icon_size: int = 18,
        color: str | None = None,
    ) -> IconTextLabel:
        return IconTextLabel(
            text=text,
            icon=cls.icon(key, color),
            object_name=object_name,
            icon_size=icon_size,
        )

    @classmethod
    def apply_button(
        cls,
        button: QPushButton,
        key: str,
        color: str | None = None,
        size: int = 18,
    ) -> None:
        if button.icon().isNull():
            button.setIcon(cls.icon(key, color))
        button.setIconSize(QSize(size, size))

    @classmethod
    def apply_action(
        cls,
        action: QAction,
        key: str,
        color: str | None = None,
    ) -> None:
        if action.icon().isNull():
            action.setIcon(cls.icon(key, color))

    @classmethod
    def clear_cache(cls) -> None:
        cls._icon_cache.clear()
