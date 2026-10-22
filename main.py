"""Fretboard Trainer entry point. Run:  python main.py"""

import sys

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import SkinManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Fretboard Trainer")
    SkinManager.instance()  # loads fonts and applies the saved theme
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
