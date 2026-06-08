"""Shared modern dialogs."""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget

from .theme import build_modern_widget_stylesheet


def confirm_delete(parent: QWidget, message: str, title: str = "Confirm Delete") -> bool:
    """Show a delete confirmation with clear Delete/Cancel buttons."""
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setText(message)
    dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    dialog.setDefaultButton(QMessageBox.StandardButton.No)

    delete_button = dialog.button(QMessageBox.StandardButton.Yes)
    cancel_button = dialog.button(QMessageBox.StandardButton.No)
    if delete_button is not None:
        delete_button.setText("Delete")
        delete_button.setObjectName("dangerButton")
    if cancel_button is not None:
        cancel_button.setText("Cancel")
        cancel_button.setObjectName("neutralButton")

    dialog.setStyleSheet(build_modern_widget_stylesheet())
    return dialog.exec() == QMessageBox.StandardButton.Yes
