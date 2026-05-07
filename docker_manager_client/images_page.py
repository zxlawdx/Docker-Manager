"""
images_page.py - Página de listagem de imagens Docker
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from grpc_client import GrpcClient


class FetchImagesWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def run(self):
        try:
            client = GrpcClient()
            images = client.list_images()
            self.finished.emit(images)
        except Exception as e:
            self.error.emit(str(e))


class ImagesPage(QWidget):

    COL_ID      = 0
    COL_REPO    = 1
    COL_TAG     = 2
    COL_SIZE    = 3
    COL_CREATED = 4

    def __init__(self):
        super().__init__()
        self._workers = []
        self._build_ui()
        self.refresh()  
    def _format_bytes(self, value):
        try:
            size = float(value)
        except (TypeError, ValueError):
            return ""

        units = ["B", "KB", "MB", "GB", "TB"]

        for unit in units:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024

        return f"{size:.2f} PB"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Cabeçalho
        header = QHBoxLayout()
        title = QLabel("Imagens")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("")
        header.addWidget(self.status_label)

        btn_refresh = QPushButton("🔄  Atualizar")
        btn_refresh.setObjectName("PrimaryButton")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(btn_refresh)

        layout.addLayout(header)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Repositório", "Tag", "Tamanho", "Criado"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

    def refresh(self):
        self._set_status("Carregando...", "orange")
        worker = FetchImagesWorker()
        worker.finished.connect(self._on_images_loaded)
        worker.error.connect(self._on_error)
        self._workers.append(worker)
        worker.start()

    def _on_images_loaded(self, images: list):
        self._set_status(f"{len(images)} imagem(ns)", "green")
        self.table.setRowCount(0)

        for img in images:
            row = self.table.rowCount()
            self.table.insertRow(row)

            id_item   = QTableWidgetItem(img.get("id", "")[:12])
            id_item.setForeground(QColor("#8b949e"))
            repo_item = QTableWidgetItem(img.get("repo", "<none>"))
            tag_item  = QTableWidgetItem(img.get("tag", "<none>"))
            size_item = QTableWidgetItem(
                self._format_bytes(img.get("size", 0))
            )
            date_item = QTableWidgetItem(img.get("created", ""))

            self.table.setItem(row, self.COL_ID,      id_item)
            self.table.setItem(row, self.COL_REPO,    repo_item)
            self.table.setItem(row, self.COL_TAG,     tag_item)
            self.table.setItem(row, self.COL_SIZE,    size_item)
            self.table.setItem(row, self.COL_CREATED, date_item)

        self.table.resizeColumnToContents(self.COL_ID)
        self.table.resizeColumnToContents(self.COL_TAG)
        self.table.resizeColumnToContents(self.COL_SIZE)

    def _on_error(self, msg: str):
        self._set_status("Erro de conexão", "red")
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar imagens:\n{msg}")

    def _set_status(self, text: str, color: str):
        colors = {"green": "#3fb950", "orange": "#d29922", "red": "#f85149"}
        hex_color = colors.get(color, "#8b949e")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {hex_color}; font-size: 12px;")
