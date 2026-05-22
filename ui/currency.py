from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QWidget


DEFAULT_CURRENCY_SYMBOL = "$"
CURRENCY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("USD ($)", "$"),
    ("RMB (\u5143)", "\u5143"),
    ("JPY (\u00a5)", "\u00a5"),
    ("RUB (\u20bd)", "\u20bd"),
)
CURRENCY_SYMBOLS = {symbol for _label, symbol in CURRENCY_OPTIONS}
MONEY_AMOUNT_PROPERTY = "moneyAmount"
MONEY_PREFIX_PROPERTY = "moneyPrefix"
MONEY_AMOUNT_ROLE = int(Qt.ItemDataRole.UserRole) + 930


def normalize_currency_symbol(value: str | None) -> str:
    clean_value = (value or "").strip()
    if clean_value in CURRENCY_SYMBOLS:
        return clean_value

    for _label, symbol in CURRENCY_OPTIONS:
        if symbol in clean_value:
            return symbol

    return DEFAULT_CURRENCY_SYMBOL


def get_currency_symbol_from_settings(getter: Callable[[str], str | None]) -> str:
    return normalize_currency_symbol(getter("currency_symbol") or getter("currency"))


def format_money(amount: float | int | str, currency_symbol: str | None = None) -> str:
    symbol = normalize_currency_symbol(currency_symbol)
    try:
        numeric_amount = float(amount)
    except (TypeError, ValueError):
        numeric_amount = 0.0
    return f"{symbol}{numeric_amount:,.2f}"


def parse_money_text(value: str, currency_symbol: str | None = None) -> float:
    clean_value = str(value or "").strip().replace(",", "")
    for symbol in CURRENCY_SYMBOLS | {normalize_currency_symbol(currency_symbol), "$"}:
        if symbol:
            clean_value = clean_value.replace(symbol, "")

    if not clean_value:
        raise ValueError("Empty amount")

    amount = float(clean_value)
    if amount < 0:
        raise ValueError("Negative amount")
    return amount


def set_money_label(
    label: QLabel,
    amount: float | int | str,
    currency_symbol: str | None = None,
    prefix: str = "",
) -> None:
    try:
        numeric_amount = float(amount or 0)
    except (TypeError, ValueError):
        numeric_amount = 0.0
    label.setProperty(MONEY_AMOUNT_PROPERTY, numeric_amount)
    label.setProperty(MONEY_PREFIX_PROPERTY, prefix)
    label.setText(f"{prefix}{format_money(numeric_amount, currency_symbol)}")


def set_money_table_item(
    item: QTableWidgetItem,
    amount: float | int | str,
    currency_symbol: str | None = None,
) -> None:
    try:
        numeric_amount = float(amount or 0)
    except (TypeError, ValueError):
        numeric_amount = 0.0
    item.setData(MONEY_AMOUNT_ROLE, numeric_amount)
    item.setText(format_money(numeric_amount, currency_symbol))


def refresh_money_widgets(root: QWidget, currency_symbol: str | None = None) -> None:
    symbol = normalize_currency_symbol(currency_symbol)

    labels = [root] if isinstance(root, QLabel) else []
    labels.extend(root.findChildren(QLabel))
    for label in labels:
        amount = label.property(MONEY_AMOUNT_PROPERTY)
        if amount is None:
            continue
        prefix = label.property(MONEY_PREFIX_PROPERTY) or ""
        label.setText(f"{prefix}{format_money(amount, symbol)}")

    tables = [root] if isinstance(root, QTableWidget) else []
    tables.extend(root.findChildren(QTableWidget))
    for table in tables:
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is None:
                    continue
                amount = item.data(MONEY_AMOUNT_ROLE)
                if amount is not None:
                    item.setText(format_money(amount, symbol))
