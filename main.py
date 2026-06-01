import sys

from PyQt6.QtWidgets import QApplication

from login import get_persisted_user, init_auth_db, show_login
from pos_terminal.pos_window import PosMainWindow, configure_app_font
from ui.app_branding import apply_app_icon


def main() -> int:
    app = QApplication(sys.argv)
    configure_app_font(app)
    apply_app_icon()
    
    # Initialize authentication database
    init_auth_db()
    
    while True:
        user = get_persisted_user() or show_login()
        if user is None:
            print("Login cancelled")
            return 0

        print(f"Logged in as: {user['full_name']} ({user['role_name']})")

        window = PosMainWindow(user_data=user)
        apply_app_icon(window)
        window.statusBar().showMessage(f"POS terminal ready - Logged in as {user['full_name']}")
        window.show()
    
        app.exec()
        if not window.logout_requested:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
