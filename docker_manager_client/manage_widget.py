import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("DockerFlow")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DockerFlow")

    app.setStyleSheet(get_global_style())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def get_global_style():
    return """
    * {
        font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
        outline: none;
    }

    QToolTip {
        background-color: #0f3460;
        color: #e0e0e0;
        border: 1px solid #00d4ff;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }
    """


if __name__ == "__main__":
    main()