"""SpaceLens — интерактивная карта диска и очистка дубликатов фото.

Запуск: python app.py
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from ui.duplicates_view import DuplicatesTab
from ui.theme import DARK_QSS
from ui.treemap_view import DiskMapTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpaceLens — анализ диска и очистка дубликатов фото")
        self.resize(1280, 820)

        tabs = QTabWidget()
        tabs.addTab(DiskMapTab(), "Карта диска")
        tabs.addTab(DuplicatesTab(), "Очистка дубликатов фото")
        self.setCentralWidget(tabs)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SpaceLens")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(DARK_QSS)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())