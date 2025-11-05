from PySide6.QtGui import QFont
import pathlib

def load_theme(app, theme_name: str = "dracula_like.qss"):
    base = pathlib.Path(__file__).resolve().parent
    candidates = [
        base / "themes" / theme_name,
        base.parent / "themes" / theme_name,
        pathlib.Path.cwd() / "themes" / theme_name,
    ]

    for p in candidates:
        if p.is_file():
            theme = p.read_text(encoding="utf-8")
            app.setStyleSheet(theme)
            app.setFont(QFont("Inter", 11))
            return

    app.setFont(QFont("Inter", 11))
