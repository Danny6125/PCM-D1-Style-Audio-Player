# main.py

import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import PCMDeckWindow


def main():
    app = QApplication(sys.argv)
    window = PCMDeckWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
