from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QWidget


DEFAULT_CURRENCY_CODE = "USD"
DEFAULT_CURRENCY_SYMBOL = "$"
CURRENCY_DATA: tuple[tuple[str, str, str], ...] = (
    ("USD", "US Dollar", "$"),
    ("EUR", "Euro", "\u20ac"),
    ("CNY", "Chinese Yuan / Renminbi", "\u5143"),
    ("JPY", "Japanese Yen", "\u00a5"),
    ("GBP", "Pound Sterling", "\u00a3"),
    ("AED", "UAE Dirham", "\u062f.\u0625"),
    ("AFN", "Afghan Afghani", "\u060b"),
    ("ALL", "Albanian Lek", "L"),
    ("AMD", "Armenian Dram", "\u058f"),
    ("ANG", "Netherlands Antillean Guilder", "NAf"),
    ("AOA", "Angolan Kwanza", "Kz"),
    ("ARS", "Argentine Peso", "AR$"),
    ("AUD", "Australian Dollar", "A$"),
    ("AWG", "Aruban Florin", "Afl"),
    ("AZN", "Azerbaijani Manat", "\u20bc"),
    ("BAM", "Bosnia-Herzegovina Convertible Mark", "KM"),
    ("BBD", "Barbadian Dollar", "Bds$"),
    ("BDT", "Bangladeshi Taka", "\u09f3"),
    ("BGN", "Bulgarian Lev", "\u043b\u0432"),
    ("BHD", "Bahraini Dinar", "BD"),
    ("BIF", "Burundian Franc", "FBu"),
    ("BMD", "Bermudian Dollar", "BD$"),
    ("BND", "Brunei Dollar", "B$"),
    ("BOB", "Bolivian Boliviano", "Bs"),
    ("BOV", "Bolivian Mvdol", "BOV"),
    ("BRL", "Brazilian Real", "R$"),
    ("BSD", "Bahamian Dollar", "B$"),
    ("BTN", "Bhutanese Ngultrum", "Nu"),
    ("BWP", "Botswana Pula", "P"),
    ("BYN", "Belarusian Ruble", "Br"),
    ("BZD", "Belize Dollar", "BZ$"),
    ("CAD", "Canadian Dollar", "CA$"),
    ("CDF", "Congolese Franc", "FC"),
    ("CHE", "WIR Euro", "CHE"),
    ("CHF", "Swiss Franc", "CHF"),
    ("CHW", "WIR Franc", "CHW"),
    ("CLF", "Chilean Unidad de Fomento", "UF"),
    ("CLP", "Chilean Peso", "CLP$"),
    ("COP", "Colombian Peso", "COL$"),
    ("COU", "Colombian Unidad de Valor Real", "COU"),
    ("CRC", "Costa Rican Colon", "\u20a1"),
    ("CUP", "Cuban Peso", "\u20b1"),
    ("CVE", "Cape Verdean Escudo", "Esc"),
    ("CZK", "Czech Koruna", "K\u010d"),
    ("DJF", "Djiboutian Franc", "Fdj"),
    ("DKK", "Danish Krone", "kr"),
    ("DOP", "Dominican Peso", "RD$"),
    ("DZD", "Algerian Dinar", "DA"),
    ("EGP", "Egyptian Pound", "E\u00a3"),
    ("ERN", "Eritrean Nakfa", "Nfk"),
    ("ETB", "Ethiopian Birr", "Br"),
    ("FJD", "Fijian Dollar", "FJ$"),
    ("FKP", "Falkland Islands Pound", "FK\u00a3"),
    ("GEL", "Georgian Lari", "\u20be"),
    ("GHS", "Ghanaian Cedi", "\u20b5"),
    ("GIP", "Gibraltar Pound", "GI\u00a3"),
    ("GMD", "Gambian Dalasi", "D"),
    ("GNF", "Guinean Franc", "FG"),
    ("GTQ", "Guatemalan Quetzal", "Q"),
    ("GYD", "Guyanese Dollar", "GY$"),
    ("HKD", "Hong Kong Dollar", "HK$"),
    ("HNL", "Honduran Lempira", "L"),
    ("HTG", "Haitian Gourde", "G"),
    ("HUF", "Hungarian Forint", "Ft"),
    ("IDR", "Indonesian Rupiah", "Rp"),
    ("ILS", "Israeli New Shekel", "\u20aa"),
    ("INR", "Indian Rupee", "\u20b9"),
    ("IQD", "Iraqi Dinar", "ID"),
    ("IRR", "Iranian Rial", "IRR"),
    ("ISK", "Icelandic Krona", "kr"),
    ("JMD", "Jamaican Dollar", "J$"),
    ("JOD", "Jordanian Dinar", "JD"),
    ("KES", "Kenyan Shilling", "KSh"),
    ("KGS", "Kyrgyzstani Som", "\u0441"),
    ("KHR", "Cambodian Riel", "\u17db"),
    ("KMF", "Comorian Franc", "CF"),
    ("KPW", "North Korean Won", "\u20a9"),
    ("KRW", "South Korean Won", "\u20a9"),
    ("KWD", "Kuwaiti Dinar", "KD"),
    ("KYD", "Cayman Islands Dollar", "CI$"),
    ("KZT", "Kazakhstani Tenge", "\u20b8"),
    ("LAK", "Lao Kip", "\u20ad"),
    ("LBP", "Lebanese Pound", "L\u00a3"),
    ("LKR", "Sri Lankan Rupee", "Rs"),
    ("LRD", "Liberian Dollar", "L$"),
    ("LSL", "Lesotho Loti", "L"),
    ("LYD", "Libyan Dinar", "LD"),
    ("MAD", "Moroccan Dirham", "DH"),
    ("MDL", "Moldovan Leu", "L"),
    ("MGA", "Malagasy Ariary", "Ar"),
    ("MKD", "Macedonian Denar", "den"),
    ("MMK", "Myanmar Kyat", "K"),
    ("MNT", "Mongolian Tugrik", "\u20ae"),
    ("MOP", "Macanese Pataca", "MOP$"),
    ("MRU", "Mauritanian Ouguiya", "UM"),
    ("MUR", "Mauritian Rupee", "Rs"),
    ("MVR", "Maldivian Rufiyaa", "Rf"),
    ("MWK", "Malawian Kwacha", "MK"),
    ("MXN", "Mexican Peso", "MX$"),
    ("MXV", "Mexican Unidad de Inversion", "MXV"),
    ("MYR", "Malaysian Ringgit", "RM"),
    ("MZN", "Mozambican Metical", "MT"),
    ("NAD", "Namibian Dollar", "N$"),
    ("NGN", "Nigerian Naira", "\u20a6"),
    ("NIO", "Nicaraguan Cordoba", "C$"),
    ("NOK", "Norwegian Krone", "kr"),
    ("NPR", "Nepalese Rupee", "Rs"),
    ("NZD", "New Zealand Dollar", "NZ$"),
    ("OMR", "Omani Rial", "OMR"),
    ("PAB", "Panamanian Balboa", "B/."),
    ("PEN", "Peruvian Sol", "S/"),
    ("PGK", "Papua New Guinean Kina", "K"),
    ("PHP", "Philippine Peso", "\u20b1"),
    ("PKR", "Pakistani Rupee", "Rs"),
    ("PLN", "Polish Zloty", "z\u0142"),
    ("PYG", "Paraguayan Guarani", "\u20b2"),
    ("QAR", "Qatari Riyal", "QR"),
    ("RON", "Romanian Leu", "lei"),
    ("RSD", "Serbian Dinar", "din"),
    ("RUB", "Russian Ruble", "\u20bd"),
    ("RWF", "Rwandan Franc", "FRw"),
    ("SAR", "Saudi Riyal", "SR"),
    ("SBD", "Solomon Islands Dollar", "SI$"),
    ("SCR", "Seychellois Rupee", "Rs"),
    ("SDG", "Sudanese Pound", "SDG"),
    ("SEK", "Swedish Krona", "kr"),
    ("SGD", "Singapore Dollar", "S$"),
    ("SHP", "Saint Helena Pound", "SH\u00a3"),
    ("SLE", "Sierra Leonean Leone", "Le"),
    ("SOS", "Somali Shilling", "Sh"),
    ("SRD", "Surinamese Dollar", "SRD$"),
    ("SSP", "South Sudanese Pound", "SS\u00a3"),
    ("STN", "Sao Tome and Principe Dobra", "Db"),
    ("SVC", "Salvadoran Colon", "SVC"),
    ("SYP", "Syrian Pound", "\u00a3S"),
    ("SZL", "Eswatini Lilangeni", "L"),
    ("THB", "Thai Baht", "\u0e3f"),
    ("TJS", "Tajikistani Somoni", "SM"),
    ("TMT", "Turkmenistani Manat", "m"),
    ("TND", "Tunisian Dinar", "DT"),
    ("TOP", "Tongan Pa'anga", "T$"),
    ("TRY", "Turkish Lira", "\u20ba"),
    ("TTD", "Trinidad and Tobago Dollar", "TT$"),
    ("TWD", "New Taiwan Dollar", "NT$"),
    ("TZS", "Tanzanian Shilling", "TSh"),
    ("UAH", "Ukrainian Hryvnia", "\u20b4"),
    ("UGX", "Ugandan Shilling", "USh"),
    ("USN", "US Dollar Next Day", "USN"),
    ("UYI", "Uruguay Peso en Unidades Indexadas", "UYI"),
    ("UYU", "Uruguayan Peso", "$U"),
    ("UYW", "Unidad Previsional", "UYW"),
    ("UZS", "Uzbekistani Som", "so'm"),
    ("VED", "Venezuelan Digital Bolivar", "Bs.D"),
    ("VES", "Venezuelan Sovereign Bolivar", "Bs.S"),
    ("VND", "Vietnamese Dong", "\u20ab"),
    ("VUV", "Vanuatu Vatu", "VT"),
    ("WST", "Samoan Tala", "WS$"),
    ("XAF", "Central African CFA Franc", "FCFA"),
    ("XAG", "Silver", "XAG"),
    ("XAU", "Gold", "XAU"),
    ("XBA", "European Composite Unit", "XBA"),
    ("XBB", "European Monetary Unit", "XBB"),
    ("XBC", "European Unit of Account 9", "XBC"),
    ("XBD", "European Unit of Account 17", "XBD"),
    ("XCD", "East Caribbean Dollar", "EC$"),
    ("XCG", "Caribbean Guilder", "Cg"),
    ("XDR", "Special Drawing Rights", "XDR"),
    ("XOF", "West African CFA Franc", "CFA"),
    ("XPD", "Palladium", "XPD"),
    ("XPF", "CFP Franc", "CFP"),
    ("XPT", "Platinum", "XPT"),
    ("XSU", "SUCRE", "XSU"),
    ("XTS", "Testing Currency Code", "XTS"),
    ("XUA", "ADB Unit of Account", "XUA"),
    ("XXX", "No Currency", "XXX"),
    ("YER", "Yemeni Rial", "YR"),
    ("ZAR", "South African Rand", "R"),
    ("ZMW", "Zambian Kwacha", "ZK"),
    ("ZWG", "Zimbabwe Gold", "ZiG"),
)
CURRENCY_OPTIONS: tuple[tuple[str, str], ...] = tuple(
    (f"{code} - {name} ({symbol})", code) for code, name, symbol in CURRENCY_DATA
)
CURRENCY_SYMBOL_BY_CODE = {code: symbol for code, _name, symbol in CURRENCY_DATA}
CURRENCY_NAME_BY_CODE = {code: name for code, name, _symbol in CURRENCY_DATA}
CURRENCY_SYMBOLS = set(CURRENCY_SYMBOL_BY_CODE.values())
MONEY_AMOUNT_PROPERTY = "moneyAmount"
MONEY_PREFIX_PROPERTY = "moneyPrefix"
MONEY_AMOUNT_ROLE = int(Qt.ItemDataRole.UserRole) + 930


def normalize_currency_code(value: str | None) -> str:
    clean_value = (value or "").strip()
    upper_value = clean_value.upper()
    if upper_value in CURRENCY_SYMBOL_BY_CODE:
        return upper_value

    for code, name, symbol in CURRENCY_DATA:
        if clean_value == symbol or code in upper_value or name.upper() in upper_value:
            return code

    return DEFAULT_CURRENCY_CODE


def normalize_currency_symbol(value: str | None) -> str:
    clean_value = (value or "").strip()
    if not clean_value:
        return DEFAULT_CURRENCY_SYMBOL

    if clean_value.upper() in CURRENCY_SYMBOL_BY_CODE:
        return CURRENCY_SYMBOL_BY_CODE[clean_value.upper()]

    if clean_value in CURRENCY_SYMBOLS:
        return clean_value

    for code, name, symbol in CURRENCY_DATA:
        label = f"{code} - {name} ({symbol})"
        if code in clean_value.upper() or name.upper() in clean_value.upper() or symbol in clean_value or clean_value in label:
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
