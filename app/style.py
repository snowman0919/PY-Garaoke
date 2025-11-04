from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame, QLineEdit, QListWidget, QProgressBar, QSplitter, QSizePolicy
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont
import sys, pathlib

def load_theme(app):
    theme = (pathlib.Path(__file__).parent / "themes" / "dracula_like.qss").read_text(encoding="utf-8")
    app.setStyleSheet(theme)
    app.setFont(QFont("Inter", 11))