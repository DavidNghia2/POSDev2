from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QEvent, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


DEFAULT_BLOCKING_TIMEOUT_MS = 90_000
CHECKOUT_TIMEOUT_MS = 90_000
PRODUCT_SYNC_TIMEOUT_MS = 120_000
USER_SYNC_TIMEOUT_MS = 90_000
BACKGROUND_SYNC_TIMEOUT_MS = 180_000


class TaskTimeoutError(RuntimeError):
    pass


class TaskCancelledError(RuntimeError):
    pass


class _TaskWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, task: Callable[[], Any]) -> None:
        super().__init__()
        self._task = task

    def run(self) -> None:
        try:
            self.succeeded.emit(self._task())
        except Exception as error:
            self.failed.emit(error)


class BlockingTaskOverlay(QFrame):
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("blockingTaskOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        card = QFrame(self)
        card.setObjectName("blockingTaskCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(12)

        self.message_label = QLabel("")
        self.message_label.setObjectName("blockingTaskMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(8)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("blockingTaskCancelButton")
        cancel_button.clicked.connect(self.cancel_requested.emit)

        card_layout.addWidget(self.message_label)
        card_layout.addWidget(progress)
        card_layout.addWidget(cancel_button, 0, Qt.AlignmentFlag.AlignCenter)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        root.addLayout(row)
        root.addStretch(1)

        self.setStyleSheet(
            """
            #blockingTaskOverlay {
                background: rgba(15, 23, 42, 138);
            }

            #blockingTaskCard {
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-radius: 10px;
                min-width: 300px;
                max-width: 390px;
            }

            #blockingTaskMessage {
                color: #111827;
                font-size: 14px;
                font-weight: 800;
            }

            #blockingTaskCancelButton {
                background: #EEF5FF;
                border: 1px solid #CFE1FF;
                border-radius: 8px;
                color: #1D4ED8;
                font-size: 13px;
                font-weight: 800;
                min-height: 34px;
                padding: 0 18px;
            }
            """
        )

    def show_message(self, message: str) -> None:
        self.message_label.setText(message)
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.setFocus()


class BlockingTaskRunner(QObject):
    _task_succeeded = pyqtSignal(int, object)
    _task_failed = pyqtSignal(int, object)

    def __init__(self, parent: QWidget, timeout_ms: int = DEFAULT_BLOCKING_TIMEOUT_MS) -> None:
        super().__init__(parent)
        self._parent_widget = parent
        self._default_timeout_ms = timeout_ms
        self._timeout_message = "This request is taking too long. Please try again."
        self._overlay = BlockingTaskOverlay(parent)
        self._overlay.cancel_requested.connect(lambda: self.cancel("Task cancelled.", timed_out=False))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._handle_timeout)
        self._active_task_id = 0
        self._is_active = False
        self._cancelled_task_ids: set[int] = set()
        self._threads: list[QThread] = []
        self._workers: list[_TaskWorker] = []
        self._on_success: Callable[[Any], None] | None = None
        self._on_error: Callable[[Exception], None] | None = None
        self._task_succeeded.connect(self._handle_success)
        self._task_failed.connect(self._handle_error)
        parent.installEventFilter(self)
        parent.destroyed.connect(self._handle_parent_destroyed)

    def start(
        self,
        task: Callable[[], Any],
        message: str,
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
        timeout_ms: int | None = None,
        timeout_message: str | None = None,
    ) -> bool:
        if self._is_active:
            return False

        self._active_task_id += 1
        task_id = self._active_task_id
        self._is_active = True
        self._on_success = on_success
        self._on_error = on_error
        self._timeout_message = timeout_message or "This request is taking too long. Please try again."
        self._overlay.show_message(message)
        self._timer.start(max(1000, timeout_ms or self._default_timeout_ms))

        thread = QThread(self)
        worker = _TaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(lambda result, tid=task_id: self._task_succeeded.emit(tid, result))
        worker.failed.connect(lambda error, tid=task_id: self._task_failed.emit(tid, error))
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(lambda _result, w=worker: self._cleanup_worker(w))
        worker.failed.connect(lambda _error, w=worker: self._cleanup_worker(w))
        worker.succeeded.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._cleanup_thread(t))
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()
        return True

    def cancel(self, message: str, timed_out: bool = False) -> None:
        if not self._is_active:
            return
        task_id = self._active_task_id
        self._cancelled_task_ids.add(task_id)
        self._finish_ui()
        callback = self._on_error
        self._clear_callbacks()
        if callback is not None:
            callback(TaskTimeoutError(message) if timed_out else TaskCancelledError(message))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        parent_widget = getattr(self, "_parent_widget", None)
        overlay = getattr(self, "_overlay", None)
        if parent_widget is not None and overlay is not None and watched is parent_widget:
            if event.type() == QEvent.Type.Resize:
                try:
                    if overlay.isVisible():
                        overlay.setGeometry(parent_widget.rect())
                except RuntimeError:
                    pass
        return False

    def _handle_timeout(self) -> None:
        self.cancel(self._timeout_message, timed_out=True)

    def _handle_success(self, task_id: int, result: Any) -> None:
        if not self._accept_result(task_id):
            return
        callback = self._on_success
        self._finish_ui()
        self._clear_callbacks()
        if callback is not None:
            callback(result)

    def _handle_error(self, task_id: int, error: Exception) -> None:
        if not self._accept_result(task_id):
            return
        callback = self._on_error
        self._finish_ui()
        self._clear_callbacks()
        if callback is not None:
            callback(error)

    def _accept_result(self, task_id: int) -> bool:
        return self._is_active and task_id == self._active_task_id and task_id not in self._cancelled_task_ids

    def _finish_ui(self) -> None:
        self._is_active = False
        self._timer.stop()
        self._overlay.hide()

    def _clear_callbacks(self) -> None:
        self._on_success = None
        self._on_error = None

    def _cleanup_thread(self, thread: QThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _cleanup_worker(self, worker: _TaskWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def _handle_parent_destroyed(self) -> None:
        self._is_active = False
        self._timer.stop()
        self._clear_callbacks()
        self._parent_widget = None


class BackgroundTaskRunner(QObject):
    _task_succeeded = pyqtSignal(object)
    _task_failed = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._is_active = False
        self._threads: list[QThread] = []
        self._workers: list[_TaskWorker] = []
        self._on_success: Callable[[Any], None] | None = None
        self._on_error: Callable[[Exception], None] | None = None
        self._task_succeeded.connect(self._handle_success)
        self._task_failed.connect(self._handle_error)

    def start(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> bool:
        if self._is_active:
            return False

        self._is_active = True
        self._on_success = on_success
        self._on_error = on_error
        thread = QThread(self)
        worker = _TaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._task_succeeded.emit)
        worker.failed.connect(self._task_failed.emit)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(lambda _result, w=worker: self._cleanup_worker(w))
        worker.failed.connect(lambda _error, w=worker: self._cleanup_worker(w))
        worker.succeeded.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._cleanup_thread(t))
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()
        return True

    def _handle_success(self, result: Any) -> None:
        callback = self._on_success
        self._set_inactive()
        if callback is not None:
            callback(result)

    def _handle_error(self, error: Exception) -> None:
        callback = self._on_error
        self._set_inactive()
        if callback is not None:
            callback(error)

    def _set_inactive(self) -> None:
        self._is_active = False
        self._on_success = None
        self._on_error = None

    def _cleanup_thread(self, thread: QThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _cleanup_worker(self, worker: _TaskWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
