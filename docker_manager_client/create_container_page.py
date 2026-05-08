"""
create_container_page.py
Tela com três abas:
  1. Compose Builder  – formulário visual por card de serviço
  2. Editor YAML      – edita docker-compose.yml cru (sincronização bidirecional)
  3. Dockerfile       – cria / edita Dockerfile com snippets de linguagem
"""

import os
import subprocess
import tempfile

import yaml

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QScrollArea,
    QComboBox, QGridLayout, QTabWidget, QPlainTextEdit,
    QFileDialog, QSplitter, QInputDialog,
)


# ══════════════════════════════════════════════════════════════
#  PALETA
# ══════════════════════════════════════════════════════════════
BG       = "#0f1117"
BG2      = "#161b27"
BG3      = "#1c2236"
BORDER   = "#2a3050"
ACCENT   = "#4f8cff"
ACCENT2  = "#7b5cf0"
TEXT     = "#dce3ff"
TEXT_DIM = "#8892b0"
GREEN    = "#3ecf8e"
RED      = "#e05c5c"
YELLOW   = "#f0b429"

TAB_STYLE = f"""
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG2};
    border-radius: 0 8px 8px 8px;
}}
QTabBar::tab {{
    background: {BG};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 9px 22px;
    font-size: 13px;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {BG2};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{ background: {BG3}; }}
"""

INPUT_STYLE = f"""
QLineEdit {{
    background: {BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

COMBO_STYLE = f"""
QComboBox {{
    background: {BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    min-width: 160px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {BG};
    color: {TEXT};
    selection-background-color: {ACCENT};
    border: 1px solid {BORDER};
}}
"""

BTN_PRIMARY = f"""
QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: white; border: none; border-radius: 7px;
    padding: 9px 24px; font-size: 13px; font-weight: bold;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6ba3ff, stop:1 #9473ff);
}}
QPushButton:disabled {{ background: {BG3}; color: #444; }}
"""

BTN_SECONDARY = f"""
QPushButton {{
    background: {BG3}; color: {TEXT_DIM};
    border: 1px solid {BORDER}; border-radius: 7px;
    padding: 9px 18px; font-size: 13px;
}}
QPushButton:hover {{ background: {BG2}; color: {TEXT}; }}
"""

BTN_GHOST = f"""
QPushButton {{
    background: transparent; color: {ACCENT};
    border: 1px dashed {ACCENT}; border-radius: 7px;
    padding: 9px 18px; font-size: 13px; font-weight: bold;
}}
QPushButton:hover {{ background: {ACCENT}22; }}
"""

BTN_DANGER = f"""
QPushButton {{
    background: transparent; color: {RED};
    border: 1px solid {RED}; border-radius: 5px;
    padding: 4px 10px; font-size: 12px;
}}
QPushButton:hover {{ background: {RED}22; }}
"""

SCROLL_STYLE = f"""
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {BG2}; width: 7px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ══════════════════════════════════════════════════════════════
#  THREAD – docker compose up
# ══════════════════════════════════════════════════════════════
class ComposeRunThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, compose_yaml: str):
        super().__init__()
        self.compose_yaml = compose_yaml

    def run(self):
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, prefix="dm_"
            ) as f:
                f.write(self.compose_yaml)
                path = f.name

            result = subprocess.run(
                ["docker", "compose", "-f", path, "up", "-d", "--build"],
                capture_output=True, text=True, timeout=300,
            )
            os.unlink(path)

            if result.returncode == 0:
                self.finished.emit(True, result.stdout or "Containers criados!")
            else:
                self.finished.emit(False, result.stderr or "Erro desconhecido.")
        except FileNotFoundError:
            self.finished.emit(False, "Docker CLI não encontrado.")
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Timeout ao criar containers.")
        except Exception as e:
            self.finished.emit(False, str(e))


# ══════════════════════════════════════════════════════════════
#  SYNTAX HIGHLIGHTERS
# ══════════════════════════════════════════════════════════════
class YamlHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        import re

        def fmt(color, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        m = re.search(r"#.*$", text)
        if m:
            self.setFormat(m.start(), len(text) - m.start(), fmt("#5c6a99"))

        for m in re.finditer(r"^\s*([\w\-]+)\s*:", text):
            self.setFormat(m.start(1), len(m.group(1)), fmt(ACCENT, bold=True))

        for m in re.finditer(r'"[^"]*"|\'[^\']*\'', text):
            self.setFormat(m.start(), m.end() - m.start(), fmt(GREEN))

        for m in re.finditer(r"\b\d+\b", text):
            self.setFormat(m.start(), m.end() - m.start(), fmt(YELLOW))

        for m in re.finditer(r"\b(true|false|yes|no|null)\b", text, re.I):
            self.setFormat(m.start(), m.end() - m.start(), fmt(YELLOW))


class DockerfileHighlighter(QSyntaxHighlighter):
    INSTRUCTIONS = [
        "FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY",
        "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD",
        "STOPSIGNAL", "HEALTHCHECK", "SHELL",
    ]

    def highlightBlock(self, text):
        import re

        def fmt(color, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        if text.strip().startswith("#"):
            self.setFormat(0, len(text), fmt("#5c6a99"))
            return

        stripped = text.strip()
        for instr in self.INSTRUCTIONS:
            if stripped.upper().startswith(instr):
                start = len(text) - len(text.lstrip())
                self.setFormat(start, len(instr), fmt(ACCENT, bold=True))
                break

        for m in re.finditer(r'"[^"]*"|\'[^\']*\'', text):
            self.setFormat(m.start(), m.end() - m.start(), fmt(GREEN))


# ══════════════════════════════════════════════════════════════
#  EDITOR DE CÓDIGO
# ══════════════════════════════════════════════════════════════
class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 12px;
                selection-background-color: {ACCENT}55;
                font-size: 13px;
            }}
        """)
        self.setTabStopDistance(32)


# ══════════════════════════════════════════════════════════════
#  PRESETS DE IMAGEM
# ══════════════════════════════════════════════════════════════
IMAGE_PRESETS = {
    "Personalizado":   {"image": "",                       "has_password": False, "default_port": "",     "env_vars": [],                                                                          "password_env": ""},
    "PostgreSQL":      {"image": "postgres:16",            "has_password": True,  "default_port": "5432", "env_vars": [("POSTGRES_USER","postgres"),("POSTGRES_DB","mydb")],                      "password_env": "POSTGRES_PASSWORD"},
    "MySQL":           {"image": "mysql:8",                "has_password": True,  "default_port": "3306", "env_vars": [("MYSQL_DATABASE","mydb"),("MYSQL_USER","user")],                          "password_env": "MYSQL_ROOT_PASSWORD"},
    "Redis":           {"image": "redis:7-alpine",         "has_password": False, "default_port": "6379", "env_vars": [],                                                                          "password_env": ""},
    "MongoDB":         {"image": "mongo:7",                "has_password": True,  "default_port": "27017","env_vars": [("MONGO_INITDB_DATABASE","mydb")],                                         "password_env": "MONGO_INITDB_ROOT_PASSWORD"},
    "Nginx":           {"image": "nginx:alpine",           "has_password": False, "default_port": "80",   "env_vars": [],                                                                          "password_env": ""},
    "Node.js":         {"image": "node:20-alpine",         "has_password": False, "default_port": "3000", "env_vars": [("NODE_ENV","production")],                                                 "password_env": ""},
    "Python / Flask":  {"image": "python:3.12-slim",       "has_password": False, "default_port": "5000", "env_vars": [("FLASK_ENV","production")],                                                "password_env": ""},
    "RabbitMQ":        {"image": "rabbitmq:3-management",  "has_password": True,  "default_port": "5672", "env_vars": [("RABBITMQ_DEFAULT_USER","admin")],                                        "password_env": "RABBITMQ_DEFAULT_PASS"},
    "Elasticsearch":   {"image": "elasticsearch:8.13.0",   "has_password": False, "default_port": "9200", "env_vars": [("discovery.type","single-node"),("xpack.security.enabled","false")],      "password_env": ""},
}


# ══════════════════════════════════════════════════════════════
#  CARD DE SERVIÇO
# ══════════════════════════════════════════════════════════════
class ServiceCard(QFrame):
    remove_requested = pyqtSignal(object)
    changed = pyqtSignal()

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self._password_env_key = ""
        self._env_rows: list = []
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            ServiceCard {{
                background: {BG3};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # cabeçalho
        hdr = QHBoxLayout()
        self.badge = QLabel(f"#{self.index}")
        self.badge.setFixedSize(28, 28)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(f"background:{ACCENT};color:white;border-radius:14px;font-weight:bold;font-size:11px;")
        hdr.addWidget(self.badge)

        self.combo_preset = QComboBox()
        self.combo_preset.addItems(IMAGE_PRESETS.keys())
        self.combo_preset.setStyleSheet(COMBO_STYLE)
        self.combo_preset.currentTextChanged.connect(self._on_preset)
        hdr.addWidget(self.combo_preset)
        hdr.addStretch()

        btn_rm = QPushButton("✕ Remover")
        btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rm.setStyleSheet(BTN_DANGER)
        btn_rm.clicked.connect(lambda: self.remove_requested.emit(self))
        hdr.addWidget(btn_rm)
        root.addLayout(hdr)

        # campos
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{TEXT_DIM};font-size:12px;")
            return l

        def inp(ph=""):
            i = QLineEdit()
            i.setPlaceholderText(ph)
            i.setStyleSheet(INPUT_STYLE)
            i.textChanged.connect(self.changed)
            return i

        grid.addWidget(lbl("Nome do serviço:"), 0, 0)
        self.inp_svc = inp("ex: db, api, cache")
        grid.addWidget(self.inp_svc, 0, 1)

        grid.addWidget(lbl("Imagem Docker:"), 0, 2)
        self.inp_image = inp("ex: nginx:alpine")
        grid.addWidget(self.inp_image, 0, 3)

        grid.addWidget(lbl("Porta host:"), 1, 0)
        self.inp_port_h = inp("ex: 5432")
        grid.addWidget(self.inp_port_h, 1, 1)

        grid.addWidget(lbl("Porta container:"), 1, 2)
        self.inp_port_c = inp("ex: 5432")
        grid.addWidget(self.inp_port_c, 1, 3)

        self.lbl_pw = lbl("Senha:")
        grid.addWidget(self.lbl_pw, 2, 0)
        self.inp_pw = inp("senha do serviço")
        grid.addWidget(self.inp_pw, 2, 1)

        grid.addWidget(lbl("Nome do container:"), 2, 2)
        self.inp_cname = inp("opcional")
        grid.addWidget(self.inp_cname, 2, 3)

        root.addLayout(grid)

        # env vars
        env_hdr = QHBoxLayout()
        env_lbl = QLabel("Variáveis de ambiente")
        env_lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:12px;font-weight:bold;")
        env_hdr.addWidget(env_lbl)
        env_hdr.addStretch()
        btn_env = QPushButton("+ var")
        btn_env.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_env.setStyleSheet(f"QPushButton{{background:transparent;color:{ACCENT};border:none;font-size:12px;}}QPushButton:hover{{color:#7ba8ff;}}")
        btn_env.clicked.connect(lambda: self._add_env())
        env_hdr.addWidget(btn_env)
        root.addLayout(env_hdr)

        self.env_layout = QVBoxLayout()
        self.env_layout.setSpacing(5)
        root.addLayout(self.env_layout)

        self._on_preset(self.combo_preset.currentText())

    def _add_env(self, key="", val=""):
        row = QHBoxLayout()
        row.setSpacing(6)
        ki = QLineEdit(); ki.setPlaceholderText("CHAVE"); ki.setText(key); ki.setStyleSheet(INPUT_STYLE); ki.textChanged.connect(self.changed)
        eq = QLabel("="); eq.setStyleSheet(f"color:{ACCENT};font-weight:bold;")
        vi = QLineEdit(); vi.setPlaceholderText("valor"); vi.setText(val); vi.setStyleSheet(INPUT_STYLE); vi.textChanged.connect(self.changed)
        bd = QPushButton("✕"); bd.setFixedSize(22, 22); bd.setCursor(Qt.CursorShape.PointingHandCursor)
        bd.setStyleSheet(f"QPushButton{{background:transparent;color:#555;border:none;font-size:13px;}}QPushButton:hover{{color:{RED};}}")
        rd = (row, ki, vi, bd)
        bd.clicked.connect(lambda: self._del_env(rd))
        row.addWidget(ki); row.addWidget(eq); row.addWidget(vi); row.addWidget(bd)
        self._env_rows.append(rd)
        self.env_layout.addLayout(row)
        self.changed.emit()

    def _del_env(self, rd):
        if rd in self._env_rows:
            self._env_rows.remove(rd)
        row, ki, vi, bd = rd
        for w in (ki, vi, bd):
            w.deleteLater()
        self.env_layout.removeItem(row)
        self.changed.emit()

    def _on_preset(self, name):
        p = IMAGE_PRESETS.get(name, IMAGE_PRESETS["Personalizado"])
        self.inp_image.setText(p["image"])
        self.inp_port_h.setText(p["default_port"])
        self.inp_port_c.setText(p["default_port"])
        self.lbl_pw.setVisible(p["has_password"])
        self.inp_pw.setVisible(p["has_password"])
        self._password_env_key = p["password_env"]
        for rd in list(self._env_rows):
            self._del_env(rd)
        for k, v in p["env_vars"]:
            self._add_env(k, v)
        if name != "Personalizado":
            self.inp_svc.setPlaceholderText(
                name.lower().split("/")[0].strip().replace(" ", "_")
            )

    def refresh_badge(self, index):
        self.index = index
        self.badge.setText(f"#{index}")

    def get_data(self):
        image = self.inp_image.text().strip()
        if not image:
            return None
        svc = self.inp_svc.text().strip() or \
              self.combo_preset.currentText().lower().split("/")[0].strip().replace(" ", "_") or \
              f"service{self.index}"
        d: dict = {"image": image}
        cn = self.inp_cname.text().strip()
        if cn:
            d["container_name"] = cn
        ph = self.inp_port_h.text().strip()
        pc = self.inp_port_c.text().strip()
        if ph and pc:
            d["ports"] = [f"{ph}:{pc}"]
        env = {}
        if self.inp_pw.isVisible() and self.inp_pw.text().strip() and self._password_env_key:
            env[self._password_env_key] = self.inp_pw.text().strip()
        for _, ki, vi, _ in self._env_rows:
            k = ki.text().strip()
            v = vi.text().strip()
            if k:
                env[k] = v
        if env:
            d["environment"] = env
        return svc, d


# ══════════════════════════════════════════════════════════════
#  ABA 1 – COMPOSE BUILDER
# ══════════════════════════════════════════════════════════════
class ComposeBuildTab(QWidget):
    yaml_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[ServiceCard] = []
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLL_STYLE)

        inner = QWidget()
        inner.setStyleSheet(f"background:{BG2};")
        self.cards_layout = QVBoxLayout(inner)
        self.cards_layout.setContentsMargins(24, 20, 24, 12)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # rodapé
        footer = QFrame()
        footer.setStyleSheet(f"background:{BG};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 12, 24, 12)
        fl.setSpacing(10)

        btn_add = QPushButton("＋  Adicionar serviço")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(BTN_GHOST)
        btn_add.clicked.connect(self._add_card)
        fl.addWidget(btn_add)
        fl.addStretch()

        self.btn_run = QPushButton("🚀  Subir containers")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setStyleSheet(BTN_PRIMARY)
        self.btn_run.clicked.connect(self._run_from_builder)
        fl.addWidget(self.btn_run)

        layout.addWidget(footer)
        self._add_card()

    def _add_card(self):
        card = ServiceCard(len(self._cards) + 1)
        card.remove_requested.connect(self._remove_card)
        card.changed.connect(self._emit_yaml)
        self._cards.append(card)
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self._emit_yaml()

    def _remove_card(self, card):
        if len(self._cards) == 1:
            QMessageBox.information(self, "Aviso", "Precisa ter ao menos 1 serviço.")
            return
        self._cards.remove(card)
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        for i, c in enumerate(self._cards, 1):
            c.refresh_badge(i)
        self._emit_yaml()

    def build_compose(self):
        services = {}
        for card in self._cards:
            r = card.get_data()
            if r is None:
                return None, card.index
            name, data = r
            if name in services:
                name = f"{name}_{card.index}"
            services[name] = data
        return {"version": "3.8", "services": services}, None

    def _emit_yaml(self):
        compose, _ = self.build_compose()
        if compose:
            self.yaml_changed.emit(
                yaml.dump(compose, default_flow_style=False, allow_unicode=True)
            )

    def load_from_yaml(self, text: str):
        try:
            data = yaml.safe_load(text)
            services = data.get("services", {}) if data else {}
        except Exception:
            return

        for card in list(self._cards):
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            self._add_card()
            card = self._cards[-1]
            card.inp_svc.setText(svc_name)
            card.inp_image.setText(svc_data.get("image", ""))
            card.inp_cname.setText(svc_data.get("container_name", ""))
            ports = svc_data.get("ports", [])
            if ports:
                parts = str(ports[0]).split(":")
                if len(parts) == 2:
                    card.inp_port_h.setText(parts[0])
                    card.inp_port_c.setText(parts[1])
            env = svc_data.get("environment", {})
            if isinstance(env, dict):
                for k, v in env.items():
                    card._add_env(k, str(v))

    def _run_from_builder(self):
        compose, bad = self.build_compose()
        if compose is None:
            QMessageBox.warning(self, "Campo obrigatório", f"Serviço #{bad} sem imagem.")
            return
        self.run_yaml(yaml.dump(compose, default_flow_style=False, allow_unicode=True))

    def run_yaml(self, yaml_text: str):
        ok = QMessageBox.question(
            self, "Confirmar", "Subir os containers com docker compose?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳  Aguarde...")
        self._thread = ComposeRunThread(yaml_text)
        self._thread.finished.connect(self._done)
        self._thread.start()

    def _done(self, success, msg):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("🚀  Subir containers")
        if success:
            QMessageBox.information(self, "Sucesso 🎉", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)


# ══════════════════════════════════════════════════════════════
#  ABA 2 – EDITOR YAML
# ══════════════════════════════════════════════════════════════
class YamlEditorTab(QWidget):
    request_load_to_builder = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sync_lock = False
        self._run_callback = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        def sbtn(label, slot):
            b = QPushButton(label)
            b.setStyleSheet(BTN_SECONDARY)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            return b

        bar.addWidget(sbtn("📂  Abrir", self._open_file))
        bar.addWidget(sbtn("💾  Salvar", self._save_file))
        bar.addWidget(sbtn("↺  Sincronizar com Builder", self._sync_to_builder))
        bar.addStretch()

        self.lbl_status = QLabel("✔ YAML válido")
        self.lbl_status.setStyleSheet(f"color:{GREEN};font-size:12px;")
        bar.addWidget(self.lbl_status)

        btn_run = QPushButton("🚀  Subir")
        btn_run.setStyleSheet(BTN_PRIMARY)
        btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_run.clicked.connect(self._run)
        bar.addWidget(btn_run)

        layout.addLayout(bar)

        self.editor = CodeEditor()
        self.editor.setPlaceholderText(
            "# Cole ou edite seu docker-compose.yml aqui\n"
            "version: '3.8'\nservices:\n  web:\n    image: nginx\n"
        )
        YamlHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._validate)
        layout.addWidget(self.editor, 1)

    def set_yaml(self, text: str):
        if self._sync_lock:
            return
        self._sync_lock = True
        cur = self.editor.textCursor()
        pos = cur.position()
        self.editor.setPlainText(text)
        cur.setPosition(min(pos, len(text)))
        self.editor.setTextCursor(cur)
        self._sync_lock = False

    def _validate(self):
        if self._sync_lock:
            return
        try:
            yaml.safe_load(self.editor.toPlainText())
            self.lbl_status.setText("✔ YAML válido")
            self.lbl_status.setStyleSheet(f"color:{GREEN};font-size:12px;")
        except Exception as e:
            self.lbl_status.setText(f"✘ {str(e)[:70]}")
            self.lbl_status.setStyleSheet(f"color:{RED};font-size:12px;")

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir docker-compose", "",
            "YAML (*.yml *.yaml);;Todos (*)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())

    def _save_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar docker-compose", "docker-compose.yml",
            "YAML (*.yml *.yaml);;Todos (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            QMessageBox.information(self, "Salvo", f"Arquivo salvo:\n{path}")

    def _sync_to_builder(self):
        self.request_load_to_builder.emit(self.editor.toPlainText())
        QMessageBox.information(
            self, "Sincronizado",
            "Conteúdo enviado para o Builder.\n"
            "Campos avançados podem não ser totalmente suportados."
        )

    def _run(self):
        if self._run_callback:
            self._run_callback(self.editor.toPlainText())


# ══════════════════════════════════════════════════════════════
#  ABA 3 – DOCKERFILE EDITOR
# ══════════════════════════════════════════════════════════════
DOCKERFILE_SNIPPETS = {
    "Node.js": (
        "FROM node:20-alpine\n"
        "WORKDIR /app\n"
        "COPY package*.json ./\n"
        "RUN npm ci --only=production\n"
        "COPY . .\n"
        "EXPOSE 3000\n"
        'CMD ["node", "index.js"]\n'
    ),
    "Python / Flask": (
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        "EXPOSE 5000\n"
        'CMD ["python", "app.py"]\n'
    ),
    "Python / FastAPI": (
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        "EXPOSE 8000\n"
        'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    ),
    "Go (multi-stage)": (
        "FROM golang:1.22-alpine AS builder\n"
        "WORKDIR /app\n"
        "COPY go.* ./\n"
        "RUN go mod download\n"
        "COPY . .\n"
        "RUN go build -o server .\n"
        "\n"
        "FROM alpine:latest\n"
        "WORKDIR /app\n"
        "COPY --from=builder /app/server .\n"
        "EXPOSE 8080\n"
        'CMD ["./server"]\n'
    ),
    "Java / Spring Boot": (
        "FROM eclipse-temurin:21-jdk-alpine AS build\n"
        "WORKDIR /app\n"
        "COPY . .\n"
        "RUN ./mvnw package -DskipTests\n"
        "\n"
        "FROM eclipse-temurin:21-jre-alpine\n"
        "WORKDIR /app\n"
        "COPY --from=build /app/target/*.jar app.jar\n"
        "EXPOSE 8080\n"
        'ENTRYPOINT ["java", "-jar", "app.jar"]\n'
    ),
    "Nginx (SPA build)": (
        "FROM node:20-alpine AS build\n"
        "WORKDIR /app\n"
        "COPY package*.json ./\n"
        "RUN npm ci\n"
        "COPY . .\n"
        "RUN npm run build\n"
        "\n"
        "FROM nginx:alpine\n"
        "COPY --from=build /app/dist /usr/share/nginx/html\n"
        "EXPOSE 80\n"
        'CMD ["nginx", "-g", "daemon off;"]\n'
    ),
    "Em branco": "FROM ubuntu:22.04\n\nWORKDIR /app\n\n",
}

DOCKERFILE_CHEATSHEET = """\
FROM <imagem>:<tag>
  Define a imagem base

WORKDIR /caminho
  Define o diretório de trabalho

COPY <src> <dest>
  Copia arquivos do host para a imagem

ADD <src> <dest>
  Como COPY, aceita URLs e arquivos tar

RUN <comando>
  Executa durante o build da imagem

ENV CHAVE=valor
  Define variável de ambiente

ARG NOME=default
  Argumento passado no build

EXPOSE <porta>
  Documenta a porta exposta

VOLUME /caminho
  Cria ponto de montagem de volume

USER <nome ou uid>
  Define o usuário de execução

CMD ["exe", "arg"]
  Comando padrão do container

ENTRYPOINT ["exe"]
  Executável principal (não sobreposto por CMD)

HEALTHCHECK CMD <cmd>
  Verifica saúde do container

LABEL chave="valor"
  Metadados da imagem

SHELL ["exe", "params"]
  Shell padrão para comandos RUN/CMD
"""


class DockerfileTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress_prompt = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        lbl = QLabel("Template:")
        lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:13px;")
        bar.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.addItems(DOCKERFILE_SNIPPETS.keys())
        self.combo.setStyleSheet(COMBO_STYLE)
        self.combo.currentTextChanged.connect(self._apply_snippet)
        bar.addWidget(self.combo)

        bar.addStretch()

        def sbtn(label, slot):
            b = QPushButton(label)
            b.setStyleSheet(BTN_SECONDARY)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            return b

        bar.addWidget(sbtn("📂  Abrir Dockerfile", self._open))
        bar.addWidget(sbtn("💾  Salvar", self._save))

        btn_build = QPushButton("🔨  docker build")
        btn_build.setStyleSheet(BTN_PRIMARY)
        btn_build.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_build.clicked.connect(self._build)
        bar.addWidget(btn_build)

        layout.addLayout(bar)

        # splitter editor | cheatsheet
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = CodeEditor()
        DockerfileHighlighter(self.editor.document())
        splitter.addWidget(self.editor)

        ref = QFrame()
        ref.setStyleSheet(f"background:{BG};border:1px solid {BORDER};border-radius:8px;")
        ref_layout = QVBoxLayout(ref)
        ref_layout.setContentsMargins(14, 12, 14, 12)
        ref_layout.setSpacing(6)

        ref_title = QLabel("📖 Referência rápida")
        ref_title.setStyleSheet(f"color:{TEXT};font-weight:bold;font-size:13px;")
        ref_layout.addWidget(ref_title)

        cheat = QPlainTextEdit()
        cheat.setReadOnly(True)
        cheat.setPlainText(DOCKERFILE_CHEATSHEET)
        cheat.setStyleSheet(f"""
            QPlainTextEdit{{
                background:{BG};color:{TEXT_DIM};
                border:none;font-family:Consolas,monospace;
                font-size:11px;
            }}
        """)
        ref_layout.addWidget(cheat, 1)
        splitter.addWidget(ref)
        splitter.setSizes([680, 240])

        layout.addWidget(splitter, 1)

        # log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet(f"""
            QPlainTextEdit{{
                background:{BG};color:{TEXT_DIM};
                border:1px solid {BORDER};border-radius:6px;
                font-family:Consolas,monospace;font-size:11px;padding:6px;
            }}
        """)
        self.log.setPlaceholderText("Output do docker build aparecerá aqui...")
        layout.addWidget(self.log)

        # aplica o primeiro snippet sem perguntar
        self._suppress_prompt = True
        self._apply_snippet(self.combo.currentText())
        self._suppress_prompt = False

    def _apply_snippet(self, name):
        content = DOCKERFILE_SNIPPETS.get(name, "")
        current = self.editor.toPlainText().strip()
        if current and not self._suppress_prompt:
            ans = QMessageBox.question(
                self, "Substituir?",
                f"Substituir o conteúdo pelo template '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.editor.setPlainText(content)

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Dockerfile", "",
            "Dockerfile (Dockerfile*);;Todos (*)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self._suppress_prompt = True
                self.editor.setPlainText(f.read())
                self._suppress_prompt = False

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Dockerfile", "Dockerfile",
            "Dockerfile (Dockerfile*);;Todos (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            QMessageBox.information(self, "Salvo", f"Salvo em:\n{path}")

    def _build(self):
        content = self.editor.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Vazio", "Escreva um Dockerfile primeiro.")
            return

        tag, ok = QInputDialog.getText(
            self, "Tag da imagem",
            "Nome e tag da imagem (ex: minha-app:latest):",
            text="minha-imagem:latest"
        )
        if not ok or not tag.strip():
            return

        tag = tag.strip()
        self.log.clear()
        self.log.appendPlainText(f"$ docker build -t {tag} .\n")

        try:
            with tempfile.TemporaryDirectory(prefix="dm_build_") as tmpdir:
                df_path = os.path.join(tmpdir, "Dockerfile")
                with open(df_path, "w", encoding="utf-8") as f:
                    f.write(content)

                result = subprocess.run(
                    ["docker", "build", "-t", tag, tmpdir],
                    capture_output=True, text=True, timeout=600,
                )

            self.log.appendPlainText(result.stdout + result.stderr)

            if result.returncode == 0:
                QMessageBox.information(
                    self, "Build OK 🎉",
                    f"Imagem '{tag}' criada com sucesso!"
                )
            else:
                QMessageBox.critical(
                    self, "Erro no build",
                    "Veja o log abaixo para detalhes."
                )
        except Exception as e:
            self.log.appendPlainText(str(e))
            QMessageBox.critical(self, "Erro", str(e))


# ══════════════════════════════════════════════════════════════
#  TELA PRINCIPAL
# ══════════════════════════════════════════════════════════════
class CreateContainerPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background:{BG2};color:{TEXT};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header
        hdr = QFrame()
        hdr.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 16, 28, 16)
        title = QLabel("🐳  Docker Manager")
        title.setStyleSheet(f"color:{TEXT};font-size:19px;font-weight:bold;")
        hl.addWidget(title)
        hl.addStretch()
        sub = QLabel("Compose Builder · Editor YAML · Dockerfile")
        sub.setStyleSheet(f"color:{TEXT_DIM};font-size:12px;")
        hl.addWidget(sub)
        layout.addWidget(hdr)

        # abas
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        self.tabs.setDocumentMode(True)

        self.tab_builder = ComposeBuildTab()
        self.tab_yaml    = YamlEditorTab()
        self.tab_docker  = DockerfileTab()

        self.tabs.addTab(self.tab_builder, "⚙  Compose Builder")
        self.tabs.addTab(self.tab_yaml,    "📝  Editor YAML")
        self.tabs.addTab(self.tab_docker,  "🐋  Dockerfile")

        # sincronização
        self.tab_builder.yaml_changed.connect(self.tab_yaml.set_yaml)
        self.tab_yaml.request_load_to_builder.connect(self.tab_builder.load_from_yaml)
        self.tab_yaml._run_callback = self.tab_builder.run_yaml

        layout.addWidget(self.tabs, 1)
   