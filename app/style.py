import os
from PySide6.QtWidgets import QApplication, QWidget

def apply_theme(app_or_widget):
    theme_file_path = os.path.join(os.path.dirname(__file__), "..", "themes", "dracula_like.qss")
    theme_file_path = os.path.abspath(theme_file_path)

    if not os.path.exists(theme_file_path):
        print(f"Warning: Theme file not found at {theme_file_path}. Application will use default style.")
        return

    try:
        with open(theme_file_path, "r", encoding="utf-8") as f:
            stylesheet = f.read()
            app_or_widget.setStyleSheet(stylesheet)
    except Exception as e:
        print(f"Error loading or applying theme from {theme_file_path}: {e}")

def load_fonts():
    # This function would be used to load custom fonts if they were to be embedded.
    # For now, it's a placeholder. PySide6 can use system fonts or fonts loaded via QFontDatabase.
    # If using QFontDatabase, it would look something like this:
    # from PySide6.QtGui import QFontDatabase
    # font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "GmarketSansTTFMedium.ttf")
    # if os.path.exists(font_path):
    #     QFontDatabase.addApplicationFont(font_path)
    pass
