from app.ui import App
from app.styles import apply_theme
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame, QLineEdit, QListWidget, QProgressBar, QSplitter, QSizePolicy
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont
import sys, pathlib

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app, "dark")
    win = App()
    load_theme(app)
    win.show()
    sys.exit(app.exec())
    
    