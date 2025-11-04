from PySide6.QtGui import QFont
import pathlib

def load_theme(app):
    theme = (pathlib.Path(__file__).parent / "themes" / "dracula_like.qss").read_text(encoding="utf-8")
    app.setStyleSheet(theme)
    app.setFont(QFont("Inter", 11))