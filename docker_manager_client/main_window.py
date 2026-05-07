"""
main_window.py - Janela principal do DockerFlow
Estrutura simples: barra lateral + área principal
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from containers_page import ContainersPage
from images_page import ImagesPage


class Sidebar(QWidget):
    """Barra lateral de navegação."""

    def __init__(self, on_navigate):
        super().__init__()
        self.on_navigate = on_navigate
        self.buttons = {}
        self._build()

    def _build(self):
        self.setFixedWidth(200)
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(6)

        # Logo / título
        logo = QLabel("🐳 DockerFlow")
        logo.setObjectName("Logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        layout.addSpacing(20)

        # Botões de navegação: (texto, ícone, página)
        nav_items = [
            ("Containers", "📦", "containers"),
            ("Imagens",    "🖼️",  "images"),
        ]

        for text, icon, page_id in nav_items:
            btn = QPushButton(f"  {icon}  {text}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, p=page_id: self.select(p))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(btn)
            self.buttons[page_id] = btn

        layout.addStretch()

        # Versão no rodapé
        version = QLabel("v1.0.0")
        version.setObjectName("Version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Seleciona o primeiro item por padrão
        self.select("containers")

    def select(self, page_id: str):
        for pid, btn in self.buttons.items():
            btn.setChecked(pid == page_id)
        self.on_navigate(page_id)


class MainWindow(QMainWindow):
    """Janela principal do aplicativo."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DockerFlow")
        self.resize(1100, 680)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        # Inicializa page_map antes da Sidebar (que chama _navigate no __init__)
        self.page_map = {}

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Barra lateral ---
        self.sidebar = Sidebar(on_navigate=self._navigate)
        root_layout.addWidget(self.sidebar)

        # Separador visual
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName("Separator")
        root_layout.addWidget(separator)

        # --- Área de páginas ---
        self.pages = QStackedWidget()
        root_layout.addWidget(self.pages, stretch=1)

        # Registra as páginas
        self.page_map = {}
        self._add_page("containers", ContainersPage())
        self._add_page("images",     ImagesPage())

    def _add_page(self, page_id: str, widget: QWidget):
        self.pages.addWidget(widget)
        self.page_map[page_id] = widget

    def _navigate(self, page_id: str):
        widget = self.page_map.get(page_id)
        if widget:
            self.pages.setCurrentWidget(widget)

    def _apply_styles(self):
        self.setStyleSheet(STYLES)


# ── Estilos globais ──────────────────────────────────────────────────────────
STYLES = """
/* Fundo geral */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}

/* Sidebar */
#Sidebar {
    background-color: #161b22;
}

#Logo {
    font-size: 16px;
    font-weight: bold;
    color: #58a6ff;
    padding: 8px 0;
}

#Version {
    font-size: 11px;
    color: #484f58;
}

/* Botões de navegação */
#NavButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    text-align: left;
    color: #8b949e;
    font-size: 13px;
}
#NavButton:hover {
    background-color: #21262d;
    color: #c9d1d9;
}
#NavButton:checked {
    background-color: #1f6feb;
    color: #ffffff;
    font-weight: bold;
}

/* Separador */
#Separator {
    color: #21262d;
    max-width: 1px;
}

/* Cabeçalho de página */
#PageTitle {
    font-size: 20px;
    font-weight: bold;
    color: #e6edf3;
}

/* Botão primário (ex: Atualizar) */
QPushButton#PrimaryButton {
    background-color: #238636;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
}
QPushButton#PrimaryButton:hover {
    background-color: #2ea043;
}
QPushButton#PrimaryButton:pressed {
    background-color: #1a7f37;
}

/* Botão de perigo (ex: Parar, Remover) */
QPushButton#DangerButton {
    background-color: #da3633;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton#DangerButton:hover {
    background-color: #f85149;
}

/* Botão neutro */
QPushButton#SecondaryButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton#SecondaryButton:hover {
    background-color: #30363d;
}

/* Tabela */
QTableWidget {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    gridline-color: #21262d;
    color: #c9d1d9;
}
QTableWidget::item {
    padding: 8px 12px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #1f3358;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #0d1117;
    color: #8b949e;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #21262d;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Status badge via texto */
QLabel#StatusRunning {
    color: #3fb950;
    font-weight: bold;
}
QLabel#StatusStopped {
    color: #f85149;
}
QLabel#StatusOther {
    color: #d29922;
}

/* Barra de status inferior */
QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #21262d;
    font-size: 12px;
}

/* Scroll */
QScrollBar:vertical {
    background: #0d1117;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""