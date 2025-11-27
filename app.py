import sys
from PySide6.QtWidgets import QApplication
from app.ui import MainWindow
from app.controller import Controller
from app.style import apply_theme

def main():
    app = QApplication(sys.argv)
    
    main_window = MainWindow()
    apply_theme(app) # Apply theme to the whole application

    # Initialize Controller after UI is set up
    controller = Controller(main_window)
    
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
