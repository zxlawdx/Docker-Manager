"""
containers_page.py - Página de gerenciamento de containers
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from grpc_client import GrpcClient


# ── Worker: busca containers em thread separada ──────────────────────────────

class FetchContainersWorker(QThread):
    """Busca a lista de containers sem travar a UI."""
    finished = pyqtSignal(list)   # lista de containers
    error    = pyqtSignal(str)    # mensagem de erro

    def run(self):
        try:
            client = GrpcClient()
            containers = client.list_containers()
            self.finished.emit(containers)
        except Exception as e:
            self.error.emit(str(e))


class ActionWorker(QThread):
    """Executa uma ação (start/stop/remove) em thread separada."""
    finished = pyqtSignal(bool, str)  # (sucesso, mensagem)

    def __init__(self, action: str, container_id: str):
        super().__init__()
        self.action = action
        self.container_id = container_id

    def run(self):
        try:
            client = GrpcClient()
            if self.action == "start":
                ok, msg = client.start_container(self.container_id)
            elif self.action == "stop":
                ok, msg = client.stop_container(self.container_id)
            elif self.action == "remove":
                ok, msg = client.remove_container(self.container_id)
            else:
                ok, msg = False, "Ação desconhecida"
            self.finished.emit(ok, msg)
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Página principal ─────────────────────────────────────────────────────────

class ContainersPage(QWidget):

    # Colunas da tabela
    COL_ID     = 0
    COL_NAME   = 1
    COL_IMAGE  = 2
    COL_STATUS = 3
    COL_PORTS  = 4

    def __init__(self):
        super().__init__()
        self._workers = []   # mantém referência para evitar garbage collection
        self._build_ui()
        self.refresh()       # carrega ao abrir

    # ── Construção da UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Cabeçalho
        header = QHBoxLayout()
        title = QLabel("📦 Containers")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusOther")
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
        self.table.setHorizontalHeaderLabels(["ID", "Nome", "Imagem", "Status", "Portas"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        # Barra de ações
        actions = QHBoxLayout()
        actions.addStretch()

        btn_start = QPushButton("▶  Start")
        btn_start.setObjectName("SecondaryButton")
        btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start.clicked.connect(lambda: self._action("start"))

        btn_stop = QPushButton("⏹  Stop")
        btn_stop.setObjectName("SecondaryButton")
        btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_stop.clicked.connect(lambda: self._action("stop"))

        btn_remove = QPushButton("🗑  Remover")
        btn_remove.setObjectName("DangerButton")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.clicked.connect(lambda: self._action("remove"))

        actions.addWidget(btn_start)
        actions.addWidget(btn_stop)
        actions.addWidget(btn_remove)
        layout.addLayout(actions)

    # ── Lógica ───────────────────────────────────────────────────────────────

    def refresh(self):
        self._set_status("Carregando...", "orange")
        worker = FetchContainersWorker()
        worker.finished.connect(self._on_containers_loaded)
        worker.error.connect(self._on_error)
        self._workers.append(worker)
        worker.start()

    def _on_containers_loaded(self, containers: list):
        self._set_status(f"{len(containers)} container(s)", "green")
        self.table.setRowCount(0)

        for c in containers:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # ID curto
            id_item = QTableWidgetItem(c.get("id", "")[:12])
            id_item.setForeground(QColor("#8b949e"))

            name_item   = QTableWidgetItem(c.get("name", ""))
            image_item  = QTableWidgetItem(c.get("image", ""))
            status_item = QTableWidgetItem(c.get("status", ""))
            ports_item  = QTableWidgetItem(c.get("ports", ""))

            # Colorir status
            status = c.get("status", "").lower()
            if "running" in status or "up" in status:
                status_item.setForeground(QColor("#3fb950"))
            elif "exited" in status or "stopped" in status:
                status_item.setForeground(QColor("#f85149"))
            else:
                status_item.setForeground(QColor("#d29922"))

            # Guarda o ID completo como dado oculto na primeira célula
            id_item.setData(Qt.ItemDataRole.UserRole, c.get("id", ""))

            self.table.setItem(row, self.COL_ID,     id_item)
            self.table.setItem(row, self.COL_NAME,   name_item)
            self.table.setItem(row, self.COL_IMAGE,  image_item)
            self.table.setItem(row, self.COL_STATUS, status_item)
            self.table.setItem(row, self.COL_PORTS,  ports_item)

        self.table.resizeColumnToContents(self.COL_ID)
        self.table.resizeColumnToContents(self.COL_STATUS)

    def _on_error(self, msg: str):
        self._set_status("Erro de conexão", "red")
        QMessageBox.critical(self, "Erro", f"Não foi possível conectar ao backend:\n{msg}")

    def _action(self, action: str):
        """Executa start/stop/remove no container selecionado."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Aviso", "Selecione um container primeiro.")
            return

        container_id = self.table.item(row, self.COL_ID).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row, self.COL_NAME).text()

        # Confirmação para ações destrutivas
        if action == "remove":
            reply = QMessageBox.question(
                self, "Confirmar",
                f"Remover o container '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._set_status(f"Executando {action}...", "orange")
        worker = ActionWorker(action, container_id)
        worker.finished.connect(lambda ok, msg: self._on_action_done(ok, msg))
        self._workers.append(worker)
        worker.start()

    def _on_action_done(self, ok: bool, msg: str):
        if ok:
            self.refresh()
        else:
            self._set_status("Erro na ação", "red")
            QMessageBox.warning(self, "Erro", msg)

    def _set_status(self, text: str, color: str):
        colors = {"green": "#3fb950", "orange": "#d29922", "red": "#f85149"}
        hex_color = colors.get(color, "#8b949e")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {hex_color}; font-size: 12px;")
