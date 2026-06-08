from pathlib import Path

root = Path(r"c:\Users\karim\Downloads\POSDev2-main\POSDev2-main final")

def replace_in_file(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Old text not found in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")

pos_path = root / "pos_terminal" / "pos_window.py"
theme_path = root / "ui" / "theme.py"

old_build_stylesheet = '''def build_stylesheet() -> str:
    return f"""
    * {{
        color: {TEXT_DARK};
        font-family: "Segoe UI";
        font-size: 13px;
    }}

    QMainWindow, QWidget {{
        background: {WINDOW_BG};
    }}

    QLabel {{
        background: transparent;
    }}

    QStatusBar {{
        background: #FFFFFF;
        border-top: 1px solid {BORDER};
        color: {TEXT_MUTED};
    }}

    #sidebar {{
        background: #FFFFFF;
        border-right: 1px solid {BORDER};
    }}

    #appTitle {{
        color: {TEXT_DARK};
        font-size: 22px;
        font-weight: 700;
    }}

    #appSubtitle, #sidebarFooter {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #sidebarBrandText {{
        background: transparent;
    }}

    #sidebarToggleButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 13px;
        min-height: 48px;
        max-height: 48px;
        min-width: 26px;
        max-width: 26px;
        padding: 0;
    }}

    #sidebarToggleButton:hover {{
        background: #F3F7FD;
        border-color: rgba(37, 99, 235, 0.35);
    }}

    #workspaceTitle {{
        font-size: 20px;
        font-weight: 700;
    }}

    #cashierInfo {{
        color: {TEXT_MUTED};
        font-size: 13px;
        font-weight: 600;
    }}

    SidebarButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 12px 14px;
        text-align: left;
    }}

    SidebarButton:hover {{
        background: #F3F7FD;
    }}

    SidebarButton[active="true"] {{
        background: rgba(37, 99, 235, 0.12);
        border-color: rgba(37, 99, 235, 0.24);
        color: {ACCENT_BLUE};
    }}

    SidebarButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton {{
        background: #DC2626;
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
        text-align: left;
    }}

    #logoutButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton:hover {{
        background: #B91C1C;
    }}

    #logoutButton:pressed {{
        background: #991B1B;
    }}

    #cardPanel, #checkoutPanel {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #panelTitle {{
        color: {TEXT_DARK};
        font-size: 20px;
        font-weight: 800;
    }}

    #panelSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 600;
    }}

    #productCard {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #productCard:hover {{
        border-color: {ACCENT_BLUE};
        background: #F8FBFF;
    }}

    #productCard[outOfStock="true"] {{
        background: #F8FAFC;
        border-color: #CBD5E1;
    }}

    #productImagePlaceholder {{
        background: #F8FAFC;
        border: 1px solid {BORDER};
        border-radius: 10px;
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #productName {{
        color: {TEXT_DARK};
        font-size: 13px;
        font-weight: 800;
    }}

    #productBarcode {{
        color: {TEXT_MUTED};
        font-size: 11px;
        font-weight: 600;
    }}

    #productPrice {{
        color: {TEXT_DARK};
        font-size: 16px;
        font-weight: 800;
    }}

    #productStock {{
        color: {ACCENT_GREEN};
        font-size: 12px;
        font-weight: 800;
    }}

    #outOfStockLabel {{
        color: #DC2626;
        font-size: 12px;
        font-weight: 800;
    }}

    #dashboardCard {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #dashboardCardTitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #dashboardCardValue {{
        color: {TEXT_DARK};
        font-size: 26px;
        font-weight: 800;
    }}

    #dashboardCardSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #dashboardActionButton {{
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 16px;
    }}

    #dashboardActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
    }}

    #dashboardActionButton[role="secondary"] {{
        background: {ACCENT_GREEN};
    }}

    QLineEdit {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px 12px;
        selection-background-color: {ACCENT_BLUE};
        selection-color: #FFFFFF;
    }}

    QLineEdit:focus {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QTableWidget {{
        alternate-background-color: #FAFBFD;
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: rgba(37, 99, 235, 0.16);
        selection-color: {TEXT_DARK};
    }}

    QHeaderView::section {{
        background: {PANEL_BG};
        border: none;
        border-bottom: 1px solid {BORDER};
        color: {TEXT_DARK};
        font-weight: 700;
        padding: 12px 10px;
    }}

    QTableWidget::item {{
        border-bottom: 1px solid #EFF3F7;
        padding: 8px 10px;
    }}

    QScrollBar:vertical {{
        background: #F3F7FD;
        border: none;
        border-left: 1px solid {BORDER};
        width: 12px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: #C1CDDA;
        border-radius: 5px;
        min-height: 32px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #9AA8B8;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    #statusHint {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    #totalBlock {{
        background: {PANEL_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    #sectionLabel {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
    }}

    #totalValue {{
        color: {TEXT_DARK};
        font-size: 34px;
        font-weight: 800;
    }}

    #amountLabel {{
        color: {TEXT_MUTED};
        font-size: 13px;
        font-weight: 700;
    }}

    #amountValue {{
        color: {TEXT_DARK};
        font-size: 15px;
        font-weight: 800;
    }}

    #discountInput {{
        max-width: 110px;
        padding: 7px 9px;
    }}

    KeypadButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 15px;
        font-weight: 700;
    }}

    KeypadButton:hover {{
        background: #F7FAFD;
        border-color: #C1CDDA;
    }}

    KeypadButton:pressed {{
        background: #EAF4FE;
        border-color: {ACCENT_BLUE};
    }}

    ActionButton {{
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
    }}

    ActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
        color: #FFFFFF;
    }}

    ActionButton[role="warning"] {{
        background: {ACCENT_ORANGE};
        color: #FFFFFF;
    }}

    ActionButton[role="neutral"] {{
        background: #E0E0E0;
        color: {TEXT_DARK};
    }}

    #payButton {{
        min-height: 52px;
        font-size: 15px;
    }}

    #splitButton, #cancelButton {{
        min-height: 48px;
    }}
    
    #tableDeleteIconButton {{
        background: transparent;
        border: none;
        color: #DC2626;
        font-size: 15px;
        font-weight: 900;
        padding: 0;
        margin-left: -12px;
        margin-top: 5px;
    }}

    #tableDeleteIconButton:hover {{
        background: #FEF2F2;
        border-radius: 14px;
        color: #B91C1C;
    }}

    #dialogTotalLabel {{
        color: {TEXT_DARK};
        font-size: 16px;
        font-weight: 700;
    }}

    #paymentDialogPanel {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}

    #paymentDialogTitle {{
        color: {TEXT_DARK};
        font-size: 22px;
        font-weight: 800;
    }}

    #paymentDialogSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 600;
    }}

    #paymentFieldLabel {{
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }}

    #paymentGrandTotal {{
        color: {TEXT_DARK};
        font-size: 32px;
        font-weight: 800;
    }}

    #amountTenderedInput {{
        font-size: 22px;
        font-weight: 800;
        padding: 14px;
    }}

    #paymentChangeValue {{
        color: {ACCENT_BLUE};
        font-size: 26px;
        font-weight: 800;
    }}

    #paymentQrPanel {{
        background: #F8FAFC;
        border: 1px dashed {BORDER};
        border-radius: 12px;
    }}

    #paymentQrPreview {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
        color: {TEXT_MUTED};
        font-size: 12px;
        font-weight: 700;
    }}

    #paymentQrDetails {{
        color: {TEXT_DARK};
        font-size: 12px;
        font-weight: 700;
    }}

    QRadioButton {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 10px;
        font-weight: 700;
        padding: 14px;
    }}

    QRadioButton:checked {{
        border-color: {ACCENT_BLUE};
        color: {ACCENT_BLUE};
    }}

    #primaryDialogButton {{
        background: {ACCENT_BLUE};
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-weight: 700;
        min-width: 140px;
        padding: 11px 18px;
    }}

    #neutralDialogButton {{
        background: #E5E7EB;
        border: none;
        border-radius: 8px;
        color: {TEXT_DARK};
        font-weight: 700;
        min-width: 120px;
        padding: 11px 18px;
    }}
    """
'''

new_build_stylesheet = '''def build_stylesheet() -> str:
    active = get_theme_mode()
    if active == THEME_DARK:
        text_dark = "#E5E7EB"
        text_muted = "#94A3B8"
        border = "#334155"
        panel_bg = "#111827"
        window_bg = "#0F172A"
        sidebar_bg = "#111827"
        sidebar_hover_bg = "#1E2937"
        sidebar_active_bg = "rgba(37, 99, 235, 0.22)"
        product_card_bg = "#111827"
        product_card_hover_bg = "#1D2937"
        product_card_out_of_stock_bg = "#111827"
        product_image_placeholder_bg = "#0F172A"
        product_image_placeholder_border = "#334155"
        dashboard_card_bg = "#111827"
        input_bg = "#111827"
        input_border = "#334155"
        table_bg = "#111827"
        table_alt_bg = "#0F172A"
        table_header_bg = "#111827"
        table_item_border = "#1F2937"
        scrollbar_bg = "#0F172A"
        scrollbar_handle = "#4B5563"
        scrollbar_handle_hover = "#6B7280"
        keypad_bg = "#111827"
        keypad_hover_bg = "#1E2937"
        keypad_pressed_bg = "#111827"
        action_neutral_bg = "#1F2937"
        action_neutral_color = "#E5E7EB"
        payment_dialog_panel_bg = "#111827"
        payment_qr_panel_bg = "#0F172A"
        payment_qr_preview_bg = "#111827"
        table_delete_hover_bg = "#1F2937"
        neutral_dialog_bg = "#1F2937"
        neutral_dialog_color = "#E5E7EB"
    else:
        text_dark = TEXT_DARK
        text_muted = TEXT_MUTED
        border = BORDER
        panel_bg = PANEL_BG
        window_bg = WINDOW_BG
        sidebar_bg = "#FFFFFF"
        sidebar_hover_bg = "#F3F7FD"
        sidebar_active_bg = "rgba(37, 99, 235, 0.12)"
        product_card_bg = "#FFFFFF"
        product_card_hover_bg = "#F8FBFF"
        product_card_out_of_stock_bg = "#F8FAFC"
        product_image_placeholder_bg = "#F8FAFC"
        product_image_placeholder_border = BORDER
        dashboard_card_bg = "#FFFFFF"
        input_bg = "#FFFFFF"
        input_border = BORDER
        table_bg = "#FFFFFF"
        table_alt_bg = "#FAFBFD"
        table_header_bg = PANEL_BG
        table_item_border = "#EFF3F7"
        scrollbar_bg = "#F3F7FD"
        scrollbar_handle = "#C1CDDA"
        scrollbar_handle_hover = "#9AA8B8"
        keypad_bg = "#FFFFFF"
        keypad_hover_bg = "#F7FAFD"
        keypad_pressed_bg = "#EAF4FE"
        action_neutral_bg = "#E0E0E0"
        action_neutral_color = TEXT_DARK
        payment_dialog_panel_bg = "#FFFFFF"
        payment_qr_panel_bg = "#F8FAFC"
        payment_qr_preview_bg = "#FFFFFF"
        table_delete_hover_bg = "#FEF2F2"
        neutral_dialog_bg = "#E5E7EB"
        neutral_dialog_color = TEXT_DARK

    return f"""
    * {{
        color: {text_dark};
        font-family: "Segoe UI";
        font-size: 13px;
    }}

    QMainWindow, QWidget {{
        background: {window_bg};
    }}

    QLabel {{
        background: transparent;
    }}

    QStatusBar {{
        background: {panel_bg};
        border-top: 1px solid {border};
        color: {text_muted};
    }}

    #sidebar {{
        background: {sidebar_bg};
        border-right: 1px solid {border};
    }}

    #appTitle {{
        color: {text_dark};
        font-size: 22px;
        font-weight: 700;
    }}

    #appSubtitle, #sidebarFooter {{
        color: {text_muted};
        font-size: 12px;
    }}

    #sidebarBrandText {{
        background: transparent;
    }}

    #sidebarToggleButton {{
        background: {sidebar_bg};
        border: 1px solid {border};
        border-radius: 13px;
        min-height: 48px;
        max-height: 48px;
        min-width: 26px;
        max-width: 26px;
        padding: 0;
    }}

    #sidebarToggleButton:hover {{
        background: {sidebar_hover_bg};
        border-color: rgba(37, 99, 235, 0.35);
    }}

    #workspaceTitle {{
        font-size: 20px;
        font-weight: 700;
    }}

    #cashierInfo {{
        color: {text_muted};
        font-size: 13px;
        font-weight: 600;
    }}

    SidebarButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 12px 14px;
        text-align: left;
    }}

    SidebarButton:hover {{
        background: {sidebar_hover_bg};
    }}

    SidebarButton[active="true"] {{
        background: {sidebar_active_bg};
        border-color: rgba(37, 99, 235, 0.24);
        color: {ACCENT_BLUE};
    }}

    SidebarButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton {{
        background: #DC2626;
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
        text-align: left;
    }}

    #logoutButton[collapsed="true"] {{
        padding: 12px 0;
        text-align: center;
    }}

    #logoutButton:hover {{
        background: #B91C1C;
    }}

    #logoutButton:pressed {{
        background: #991B1B;
    }}

    #cardPanel, #checkoutPanel {{
        background: {panel_bg};
        border: 1px solid {border};
        border-radius: 10px;
    }}

    #panelTitle {{
        color: {text_dark};
        font-size: 20px;
        font-weight: 800;
    }}

    #panelSubtitle {{
        color: {text_muted};
        font-size: 12px;
        font-weight: 600;
    }}

    #productCard {{
        background: {product_card_bg};
        border: 1px solid {border};
        border-radius: 10px;
    }}

    #productCard:hover {{
        border-color: {ACCENT_BLUE};
        background: {product_card_hover_bg};
    }}

    #productCard[outOfStock="true"] {{
        background: {product_card_out_of_stock_bg};
        border-color: #CBD5E1;
    }}

    #productImagePlaceholder {{
        background: {product_image_placeholder_bg};
        border: 1px solid {product_image_placeholder_border};
        border-radius: 10px;
        color: {text_muted};
        font-size: 12px;
        font-weight: 700;
    }}

    #productName {{
        color: {text_dark};
        font-size: 13px;
        font-weight: 800;
    }}

    #productBarcode {{
        color: {text_muted};
        font-size: 11px;
        font-weight: 600;
    }}

    #productPrice {{
        color: {text_dark};
        font-size: 16px;
        font-weight: 800;
    }}

    #productStock {{
        color: {ACCENT_GREEN};
        font-size: 12px;
        font-weight: 800;
    }}

    #outOfStockLabel {{
        color: #DC2626;
        font-size: 12px;
        font-weight: 800;
    }}

    #dashboardCard {{
        background: {dashboard_card_bg};
        border: 1px solid {border};
        border-radius: 10px;
    }}

    #dashboardCardTitle {{
        color: {text_muted};
        font-size: 12px;
        font-weight: 700;
    }}

    #dashboardCardValue {{
        color: {text_dark};
        font-size: 26px;
        font-weight: 800;
    }}

    #dashboardCardSubtitle {{
        color: {text_muted};
        font-size: 12px;
    }}

    #dashboardActionButton {{
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 16px;
    }}

    #dashboardActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
    }}

    #dashboardActionButton[role="secondary"] {{
        background: {ACCENT_GREEN};
    }}

    QLineEdit {{
        background: {input_bg};
        border: 1px solid {input_border};
        border-radius: 8px;
        padding: 10px 12px;
        selection-background-color: {ACCENT_BLUE};
        selection-color: #FFFFFF;
    }}

    QLineEdit:focus {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QTableWidget {{
        alternate-background-color: {table_alt_bg};
        background: {table_bg};
        border: 1px solid {border};
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: rgba(37, 99, 235, 0.16);
        selection-color: {text_dark};
    }}

    QHeaderView::section {{
        background: {table_header_bg};
        border: none;
        border-bottom: 1px solid {border};
        color: {text_dark};
        font-weight: 700;
        padding: 12px 10px;
    }}

    QTableWidget::item {{
        border-bottom: 1px solid {table_item_border};
        padding: 8px 10px;
    }}

    QScrollBar:vertical {{
        background: {scrollbar_bg};
        border: none;
        border-left: 1px solid {border};
        width: 12px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {scrollbar_handle};
        border-radius: 5px;
        min-height: 32px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {scrollbar_handle_hover};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    #statusHint {{
        color: {text_muted};
        font-size: 12px;
    }}

    #totalBlock {{
        background: {panel_bg};
        border: 1px solid {border};
        border-radius: 10px;
    }}

    #sectionLabel {{
        color: {text_muted};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
    }}

    #totalValue {{
        color: {text_dark};
        font-size: 34px;
        font-weight: 800;
    }}

    #amountLabel {{
        color: {text_muted};
        font-size: 13px;
        font-weight: 700;
    }}

    #amountValue {{
        color: {text_dark};
        font-size: 15px;
        font-weight: 800;
    }}

    #discountInput {{
        max-width: 110px;
        padding: 7px 9px;
    }}

    KeypadButton {{
        background: {keypad_bg};
        border: 1px solid {border};
        border-radius: 8px;
        font-size: 15px;
        font-weight: 700;
    }}

    KeypadButton:hover {{
        background: {keypad_hover_bg};
        border-color: {border};
    }}

    KeypadButton:pressed {{
        background: {keypad_pressed_bg};
        border-color: {ACCENT_BLUE};
    }}

    ActionButton {{
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 14px;
    }}

    ActionButton[role="primary"] {{
        background: {ACCENT_BLUE};
        color: #FFFFFF;
    }}

    ActionButton[role="warning"] {{
        background: {ACCENT_ORANGE};
        color: #FFFFFF;
    }}

    ActionButton[role="neutral"] {{
        background: {action_neutral_bg};
        color: {action_neutral_color};
    }}

    #payButton {{
        min-height: 52px;
        font-size: 15px;
    }}

    #splitButton, #cancelButton {{
        min-height: 48px;
    }}
    
    #tableDeleteIconButton {{
        background: transparent;
        border: none;
        color: #DC2626;
        font-size: 15px;
        font-weight: 900;
        padding: 0;
        margin-left: -12px;
        margin-top: 5px;
    }}

    #tableDeleteIconButton:hover {{
        background: {table_delete_hover_bg};
        border-radius: 14px;
        color: #B91C1C;
    }}

    #dialogTotalLabel {{
        color: {text_dark};
        font-size: 16px;
        font-weight: 700;
    }}

    #paymentDialogPanel {{
        background: {payment_dialog_panel_bg};
        border: 1px solid {border};
        border-radius: 14px;
    }}

    #paymentDialogTitle {{
        color: {text_dark};
        font-size: 22px;
        font-weight: 800;
    }}

    #paymentDialogSubtitle {{
        color: {text_muted};
        font-size: 12px;
        font-weight: 600;
    }}

    #paymentFieldLabel {{
        color: {text_muted};
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }}

    #paymentGrandTotal {{
        color: {text_dark};
        font-size: 32px;
        font-weight: 800;
    }}

    #amountTenderedInput {{
        font-size: 22px;
        font-weight: 800;
        padding: 14px;
    }}

    #paymentChangeValue {{
        color: {ACCENT_BLUE};
        font-size: 26px;
        font-weight: 800;
    }}

    #paymentQrPanel {{
        background: {payment_qr_panel_bg};
        border: 1px dashed {border};
        border-radius: 12px;
    }}

    #paymentQrPreview {{
        background: {payment_qr_preview_bg};
        border: 1px solid {border};
        border-radius: 10px;
        color: {text_muted};
        font-size: 12px;
        font-weight: 700;
    }}

    #paymentQrDetails {{
        color: {text_dark};
        font-size: 12px;
        font-weight: 700;
    }}

    QRadioButton {{
        background: {input_bg};
        border: 1px solid {border};
        border-radius: 10px;
        font-weight: 700;
        padding: 14px;
    }}

    QRadioButton:checked {{
        border-color: {ACCENT_BLUE};
        color: {ACCENT_BLUE};
    }}

    #primaryDialogButton {{
        background: {ACCENT_BLUE};
        border: none;
        border-radius: 8px;
        color: #FFFFFF;
        font-weight: 700;
        min-width: 140px;
        padding: 11px 18px;
    }}

    #neutralDialogButton {{
        background: {neutral_dialog_bg};
        border: none;
        border-radius: 8px;
        color: {neutral_dialog_color};
        font-weight: 700;
        min-width: 120px;
        padding: 11px 18px;
    }}
    """
'''

old_theme_block = '''    if active == THEME_DARK:
        return f"""
QWidget {{
    color: #E5E7EB;
    font-family: "Segoe UI";
    font-size: 13px;
}}

QLabel {{
    background: transparent;
}}

QFrame#panel,
QFrame#cardPanel,
QFrame#checkoutPanel,
QFrame#dialogPanel,
QFrame#paymentDialogPanel,
QFrame#qrPreviewCard {{
    border-radius: 14px;
}}

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #E5E7EB;
    min-height: 18px;
    padding: 7px 10px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}}

QLineEdit:hover,
QComboBox:hover,
QDateEdit:hover,
QTextEdit:hover {{
    border-color: #475569;
}}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus {{
    border: 1px solid #2563EB;
}}

QComboBox {{
    combobox-popup: 0;
    padding-right: 30px;
}}

QComboBox::drop-down,
QDateEdit::drop-down {{
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
}}

QComboBox QAbstractItemView {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 0;
    outline: 0;
    padding: 0;
    margin: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}}

QComboBox QAbstractItemView::item {{
    background: #111827;
    color: #E5E7EB;
    min-height: 28px;
    padding: 6px 10px;
}}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background: #2563EB;
    color: #FFFFFF;
}}

QCheckBox {{
    background: transparent;
    color: #E5E7EB;
    font-weight: 650;
    spacing: 7px;
}}

QCheckBox::indicator {{
    background: #111827;
    border: 1px solid #64748B;
    border-radius: 5px;
    height: 17px;
    width: 17px;
}}

QCheckBox::indicator:hover {{
    border-color: #2563EB;
}}

QCheckBox::indicator:checked {{
    background: #2563EB;
    border-color: #2563EB;
    image: url("{CHECK_ICON_URL}");
}}

QRadioButton {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    color: #E5E7EB;
    font-weight: 750;
    padding: 8px 11px;
    spacing: 7px;
}}

QRadioButton:hover {{
    background: #0F172A;
    border-color: #475569;
}}

QRadioButton:checked {{
    background: #0B1220;
    border-color: #2563EB;
    color: #93C5FD;
}}

QRadioButton::indicator {{
    background: #111827;
    border: 1px solid #64748B;
    border-radius: 7px;
    height: 15px;
    width: 15px;
}}

QRadioButton::indicator:checked {{
    background: #111827;
    border: 2px solid #2563EB;
    border-radius: 7px;
    image: url("{RADIO_DOT_ICON_URL}");
}}

QPushButton {{
    border: none;
    border-radius: 8px;
    font-weight: 750;
    min-height: 30px;
    min-width: 74px;
    padding: 5px 11px;
}}

QPushButton:pressed {{
    padding-top: 6px;
    padding-bottom: 4px;
}}

QPushButton:disabled {{
    background: #334155;
    color: #94A3B8;
}}

#primaryButton,
#primaryDialogButton,
#dashboardActionButton[role="primary"],
#rowEditButton,
#smallButton {{
    background: #2563EB;
    color: #FFFFFF;
}}

#primaryButton:hover,
#primaryDialogButton:hover,
#dashboardActionButton[role="primary"]:hover,
#rowEditButton:hover,
#smallButton:hover {{
    background: #1D4ED8;
}}

#secondaryButton,
#dashboardActionButton[role="secondary"] {{
    background: #0F766E;
    color: #FFFFFF;
}}

#secondaryButton:hover,
#dashboardActionButton[role="secondary"]:hover {{
    background: #0D5F59;
}}

#dangerButton,
#rowDeleteButton {{
    background: #DC2626;
    color: #FFFFFF;
}}

#dangerButton:hover,
#rowDeleteButton:hover {{
    background: #B91C1C;
}}

#neutralButton,
#neutralDialogButton {{
    background: #334155;
    color: #E5E7EB;
}}

#neutralButton:hover,
#neutralDialogButton:hover {{
    background: #475569;
}}

#primaryButton,
#secondaryButton,
#dangerButton,
#neutralButton,
#primaryDialogButton,
#neutralDialogButton,
#dashboardActionButton {{
    min-height: 32px;
    min-width: 82px;
    padding: 6px 12px;
}}

#primaryDialogButton,
#neutralDialogButton {{
    min-width: 96px;
    max-width: 150px;
}}

#rowEditButton,
#rowDeleteButton,
#smallButton {{
    min-height: 28px;
    min-width: 72px;
    padding: 4px 9px;
}}

KeypadButton {{
    min-height: 46px;
}}

ActionButton {{
    min-height: 42px;
    padding: 8px 12px;
}}

#payButton {{
    min-height: 46px;
    font-size: 14px;
}}

#splitButton,
#cancelButton {{
    min-height: 42px;
}}

QTableWidget {{
    alternate-background-color: #0F172A;
    background: #111827;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #1E3A8A;
    selection-color: #E5E7EB;
}}

QHeaderView::section {{
    background: #0F172A;
    border: none;
    border-bottom: 1px solid #334155;
    color: #CBD5E1;
    font-weight: 800;
    padding: 11px 10px;
}}

QTableWidget::item {{
    border-bottom: 1px solid #1E293B;
    padding: 8px 10px;
}}

QTableWidget::item:selected {{
    background: #1E3A8A;
    color: #E5E7EB;
}}

QMessageBox {{
    background: #0F172A;
}}

QMessageBox QLabel {{
    background: transparent;
    color: #E5E7EB;
    font-size: 13px;
}}

QMessageBox QPushButton {{
    background: #2563EB;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 750;
    max-width: 110px;
    min-height: 32px;
    min-width: 76px;
    padding: 6px 12px;
}}

QMessageBox QPushButton:hover {{
    background: #1D4ED8;
}}

QScrollBar:vertical {{
    background: #0F172A;
    border: none;
    width: 12px;
}}

QScrollBar::handle:vertical {{
    background: #475569;
    border-radius: 6px;
    min-height: 34px;
}}

QScrollBar::handle:vertical:hover {{
    background: #64748B;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    border: none;
    height: 0;
}}
"""
'''

new_theme_block = '''    if active == THEME_DARK:
        return f"""
QWidget {
    color: #E5E7EB;
    font-family: "Segoe UI";
    font-size: 13px;
    background: #0F172A;
}

QDialog, QFrame, QScrollArea, QListView, QAbstractItemView, QMenu, QMenuBar {
    background: #111827;
}

QLabel {
    background: transparent;
}

QFrame#panel,
QFrame#cardPanel,
QFrame#checkoutPanel,
QFrame#dialogPanel,
QFrame#paymentDialogPanel,
QFrame#qrPreviewCard {
    border-radius: 14px;
}

QPushButton {
    background: #1F2937;
    color: #E5E7EB;
    border: none;
    border-radius: 8px;
    font-weight: 750;
    min-height: 30px;
    min-width: 74px;
    padding: 5px 11px;
}

QPushButton:hover {
    background: #111827;
}

QPushButton:pressed {
    padding-top: 6px;
    padding-bottom: 4px;
    background: #0B1220;
}

QPushButton:disabled {
    background: #334155;
    color: #94A3B8;
}

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #E5E7EB;
    min-height: 18px;
    padding: 7px 10px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QLineEdit:hover,
QComboBox:hover,
QDateEdit:hover,
QTextEdit:hover {
    border-color: #475569;
}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus {
    border: 1px solid #2563EB;
}

QComboBox {
    combobox-popup: 0;
    padding-right: 30px;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
}

QComboBox QAbstractItemView {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 0;
    outline: 0;
    padding: 0;
    margin: 0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QComboBox QAbstractItemView::item {
    background: #111827;
    color: #E5E7EB;
    min-height: 28px;
    padding: 6px 10px;
}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {
    background: #2563EB;
    color: #FFFFFF;
}

QCheckBox {
    background: transparent;
    color: #E5E7EB;
    font-weight: 650;
    spacing: 7px;
}

QCheckBox::indicator {
    background: #111827;
    border: 1px solid #64748B;
    border-radius: 5px;
    height: 17px;
    width: 17px;
}

QCheckBox::indicator:hover {
    border-color: #2563EB;
}

QCheckBox::indicator:checked {
    background: #2563EB;
    border-color: #2563EB;
    image: url("{CHECK_ICON_URL}");
}

QRadioButton {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    color: #E5E7EB;
    font-weight: 750;
    padding: 8px 11px;
    spacing: 7px;
}

QRadioButton:hover {
    background: #0F172A;
    border-color: #475569;
}

QRadioButton:checked {
    background: #0B1220;
    border-color: #2563EB;
    color: #93C5FD;
}

QRadioButton::indicator {
    background: #111827;
    border: 1px solid #64748B;
    border-radius: 7px;
    height: 15px;
    width: 15px;
}

QRadioButton::indicator:checked {
    background: #111827;
    border: 2px solid #2563EB;
    border-radius: 7px;
    image: url("{RADIO_DOT_ICON_URL}");
}

#primaryButton,
#primaryDialogButton,
#dashboardActionButton[role="primary"],
#rowEditButton,
#smallButton {
    background: #2563EB;
    color: #FFFFFF;
}

#primaryButton:hover,
#primaryDialogButton:hover,
#dashboardActionButton[role="primary"]:hover,
#rowEditButton:hover,
#smallButton:hover {
    background: #1D4ED8;
}

#secondaryButton,
#dashboardActionButton[role="secondary"] {
    background: #0F766E;
    color: #FFFFFF;
}

#secondaryButton:hover,
#dashboardActionButton[role="secondary"]:hover {
    background: #0D5F59;
}

#dangerButton,
#rowDeleteButton {
    background: #DC2626;
    color: #FFFFFF;
}

#dangerButton:hover,
#rowDeleteButton:hover {
    background: #B91C1C;
}

#neutralButton,
#neutralDialogButton {
    background: #334155;
    color: #E5E7EB;
}

#neutralButton:hover,
#neutralDialogButton:hover {
    background: #475569;
}

#primaryButton,
#secondaryButton,
#dangerButton,
#neutralButton,
#primaryDialogButton,
#neutralDialogButton,
#dashboardActionButton {
    min-height: 32px;
    min-width: 82px;
    padding: 6px 12px;
}

#primaryDialogButton,
#neutralDialogButton {
    min-width: 96px;
    max-width: 150px;
}

#rowEditButton,
#rowDeleteButton,
#smallButton {
    min-height: 28px;
    min-width: 72px;
    padding: 4px 9px;
}

KeypadButton {
    min-height: 46px;
}

ActionButton {
    min-height: 42px;
    padding: 8px 12px;
}

#payButton {
    min-height: 46px;
    font-size: 14px;
}

#splitButton,
#cancelButton {
    min-height: 42px;
}

QTableWidget {
    alternate-background-color: #0F172A;
    background: #111827;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #1E3A8A;
    selection-color: #E5E7EB;
}

QHeaderView::section {
    background: #0F172A;
    border: none;
    border-bottom: 1px solid #334155;
    color: #CBD5E1;
    font-weight: 800;
    padding: 11px 10px;
}

QTableWidget::item {
    border-bottom: 1px solid #1E293B;
    padding: 8px 10px;
}

QTableWidget::item:selected {
    background: #1E3A8A;
    color: #E5E7EB;
}

QMessageBox {
    background: #0F172A;
}

QMessageBox QLabel {
    background: transparent;
    color: #E5E7EB;
    font-size: 13px;
}

QMessageBox QPushButton {
    background: #2563EB;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 750;
    max-width: 110px;
    min-height: 32px;
    min-width: 76px;
    padding: 6px 12px;
}

QMessageBox QPushButton:hover {
    background: #1D4ED8;
}

QScrollBar:vertical {
    background: #0F172A;
    border: none;
    width: 12px;
}

QScrollBar::handle:vertical {
    background: #475569;
    border-radius: 6px;
    min-height: 34px;
}

QScrollBar::handle:vertical:hover {
    background: #64748B;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0;
}
"""
'''

replace_in_file(pos_path, old_build_stylesheet, new_build_stylesheet)
replace_in_file(theme_path, old_theme_block, new_theme_block)
print("Patch applied successfully")
