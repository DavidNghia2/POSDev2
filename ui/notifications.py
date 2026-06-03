from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtNetwork import QNetworkInformation
from PyQt6.QtWidgets import QLabel, QMainWindow, QWidget


NETWORK_ERROR_MESSAGE = "Cannot connect to the network. Check your internet connection and try again."
UNKNOWN_ERROR_MESSAGE = "Something went wrong. Please try again."


def _error_text(error: Any) -> str:
    if error is None:
        return ""
    try:
        return str(error)
    except Exception:
        return ""


def friendly_error(error: Any) -> str:
    text = _error_text(error)
    lower = text.lower()

    if not text:
        return UNKNOWN_ERROR_MESSAGE
    if any(token in lower for token in ("timeout", "timed out", "network", "connection", "offline", "dns", "httpx")):
        return NETWORK_ERROR_MESSAGE
    if any(token in lower for token in ("missing supabase", "supabase is not configured", "supabase configuration", ".env")):
        return "Supabase is not configured. Check your .env settings."
    if any(token in lower for token in ("schema is not installed", "db push", "function", "edge function")):
        return "The cloud setup is not ready. Please check Supabase migrations and functions."
    if "session" in lower and any(token in lower for token in ("expired", "missing", "restore", "remembered")):
        return "Your session has expired. Please log in again."
    if any(token in lower for token in ("unauthorized", "permission", "row-level security", "rls", "policy", "forbidden", "only store admins")):
        return "You do not have permission to perform this action."
    if any(token in lower for token in ("duplicate", "unique constraint", "already exists", "conflict")):
        return "This value already exists. Please use a different one."
    if any(token in lower for token in ("permission denied", "file", "directory", "no such file", "cannot access")):
        return "Could not access the selected file. Check the file path and permissions."
    if any(token in lower for token in ("out of stock", "insufficient stock", "stock changed", "stock", "inventory")):
        return "Stock changed or is no longer available. Please sync and try again."
    if any(token in lower for token in ("bucket", "storage", "image upload", "upload")):
        return "Could not upload the image. Check storage settings and try again."
    if any(token in lower for token in ("invalid login", "invalid credentials", "email not confirmed")):
        return "The email or password is incorrect."
    if any(token in lower for token in ("taking too long", "try again")):
        return text if len(text) <= 180 else UNKNOWN_ERROR_MESSAGE
    return UNKNOWN_ERROR_MESSAGE


@dataclass(frozen=True)
class NotificationStyle:
    background: str
    border: str
    text: str


NOTIFICATION_STYLES = {
    "success": NotificationStyle("#ECFDF5", "#A7F3D0", "#047857"),
    "info": NotificationStyle("#EFF6FF", "#BFDBFE", "#1D4ED8"),
    "warning": NotificationStyle("#FFFBEB", "#FDE68A", "#B45309"),
    "error": NotificationStyle("#FEF2F2", "#FECACA", "#B91C1C"),
}


class NotificationProvider:
    def __init__(self, parent: QMainWindow, anchor: QWidget | None = None) -> None:
        self.parent = parent
        self.anchor = anchor or parent
        self.toast = QLabel(self.anchor)
        self.toast.setObjectName("globalNotificationToast")
        self.toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast.setWordWrap(True)
        self.toast.hide()

    def notify_success(self, message: str) -> None:
        self._show(message, "success")

    def notify_info(self, message: str) -> None:
        self._show(message, "info")

    def notify_warning(self, message: str) -> None:
        self._show(message, "warning")

    def notify_error(self, message: str) -> None:
        self._show(message, "error")

    def position(self) -> None:
        margin = 24
        self.toast.adjustSize()
        x = max(margin, self.anchor.width() - self.toast.width() - margin)
        self.toast.move(x, margin)
        self.toast.raise_()

    def _show(self, message: str, level: str) -> None:
        style = NOTIFICATION_STYLES.get(level, NOTIFICATION_STYLES["info"])
        self.toast.setText(message)
        self.toast.setStyleSheet(
            f"""
            #globalNotificationToast {{
                background: {style.background};
                border: 1px solid {style.border};
                border-radius: 8px;
                color: {style.text};
                font-size: 13px;
                font-weight: 800;
                padding: 10px 14px;
            }}
            """
        )
        self.toast.adjustSize()
        self.toast.setFixedWidth(min(max(self.toast.width() + 26, 260), 440))
        self.position()
        self.toast.show()
        self.toast.raise_()
        self.parent.statusBar().showMessage(message, 5000)
        QTimer.singleShot(3000, self.toast.hide)


class NetworkStatusProvider:
    def __init__(self, parent: QWidget, on_offline: Callable[[], None], on_online: Callable[[], None]) -> None:
        self.parent = parent
        self.on_offline = on_offline
        self.on_online = on_online
        if QNetworkInformation.instance() is None:
            QNetworkInformation.loadDefaultBackend()
        self.network_info = QNetworkInformation.instance()
        self.was_reachable: bool | None = None
        self.poll_timer = QTimer(parent)
        self.poll_timer.setInterval(3000)
        self.poll_timer.timeout.connect(self.check_reachability)

        if self.network_info is not None:
            self.network_info.reachabilityChanged.connect(lambda _reachability: self.check_reachability())
        self.check_reachability()
        self.poll_timer.start()

    def check_reachability(self) -> None:
        reachable = self.is_reachable()
        if self.was_reachable is None:
            self.was_reachable = reachable
            return
        if reachable == self.was_reachable:
            return
        self.was_reachable = reachable
        if reachable:
            self.on_online()
        else:
            self.on_offline()

    def is_reachable(self) -> bool:
        if self.network_info is None:
            return True
        reachability = self.network_info.reachability()
        return reachability != QNetworkInformation.Reachability.Disconnected
