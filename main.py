import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from login import show_login, init_auth_db
from pos_terminal.pos_window import PosMainWindow, configure_app_font


def main() -> int:
    app = QApplication(sys.argv)
    configure_app_font(app)
    
    # Initialize authentication database
    init_auth_db()
    
    # Show login dialog
    user = show_login()
    
    if user is None:
        print("Login cancelled")
        return 0
    
    print(f"Logged in as: {user['full_name']} ({user['role_name']})")
    
    # Create main window with user data
    window = PosMainWindow(user_data=user)
    window.statusBar().showMessage(f"POS terminal ready - Logged in as {user['full_name']}")
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
