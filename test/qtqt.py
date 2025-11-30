import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLineEdit, QPushButton, QGridLayout, QVBoxLayout

class Calculator(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("간단한 계산기")
        self.setGeometry(100, 100, 300, 400)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.result_display = QLineEdit()
        self.result_display.setReadOnly(True)
        main_layout.addWidget(self.result_display)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)
        buttons = [
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            'C', '0', '=', '+'
        ]
        row = 0
        col = 0
        for text in buttons:
            button = QPushButton(text)
            grid_layout.addWidget(button, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
if __name__ == '__main__':
    app = QApplication(sys.argv)
    calc = Calculator()
    calc.show()
    sys.exit(app.exec())
