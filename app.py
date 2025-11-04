from PySide6.QtWidgets import QApplication
from app.ui_modern import ModernMainWindow
from app.styles import apply_theme
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app, "dark")
    win = ModernMainWindow()
    win.show()
    sys.exit(app.exec())