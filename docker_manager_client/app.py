"""
app.py - Ponto de entrada do DockerFlow
Execute: python app.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from main_window import MainWindow, STYLES


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DockerFlow")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DockerFlow")
    app.setStyleSheet(STYLES)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
