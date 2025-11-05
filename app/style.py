from PySide6.QtGui import QFont
import pathlib

def load_theme(app, theme_name: str = "dracula_like.qss"):
    base = pathlib.Path(__file__).resolve().parent
    candidates = [
        base / "themes" / theme_name,          # app/themes
        base.parent / "themes" / theme_name,   # project-level themes
        pathlib.Path.cwd() / "themes" / theme_name,  # CWD/themes (fallback)
    ]

    for p in candidates:
        if p.is_file():
            theme = p.read_text(encoding="utf-8")
            app.setStyleSheet(theme)
            app.setFont(QFont("Inter", 11))
            return

    # Fallback: set font only if theme not found
    app.setFont(QFont("Inter", 11))
