"""
terminal_page.py
Terminal Docker cross-platform
Windows / Linux / macOS

Abre um terminal REAL do sistema operacional
conectando diretamente no container Docker.
"""

import platform
import shlex
import shutil

from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
    QTextEdit,
    QSizePolicy,
    QMessageBox,
)

from grpc_client import GrpcClient


# =========================================================
# CORES
# =========================================================
BG = "#0d1117"
BG2 = "#161b22"
BG3 = "#21262d"

BORDER = "#30363d"

ACCENT = "#58a6ff"

TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"

GREEN = "#3fb950"
RED = "#f85149"

TERM_BG = "#010409"
TERM_FG = "#e6edf3"


# =========================================================
# TERMINAL PAGE
# =========================================================
class TerminalPage(QWidget):

    def __init__(self):
        super().__init__()

        self.containers = []

        self._build_ui()

        self.load_containers()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self):

        self.setStyleSheet(
            f"background-color: {BG}; color: {TEXT};"
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # =================================================
        # HEADER
        # =================================================
        header = QFrame()

        header.setStyleSheet(f"""
            QFrame {{
                background-color: {BG2};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        header_layout = QHBoxLayout(header)

        header_layout.setContentsMargins(
            24, 14, 24, 14
        )

        title = QLabel("⌨ Terminal Docker")

        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
        """)

        header_layout.addWidget(title)

        header_layout.addStretch()

        self.status_label = QLabel("● pronto")

        self.status_label.setStyleSheet(
            f"color: {GREEN};"
        )

        header_layout.addWidget(self.status_label)

        root.addWidget(header)

        # =================================================
        # CONTROLS
        # =================================================
        controls = QFrame()

        controls.setStyleSheet(f"""
            QFrame {{
                background-color: {BG2};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        controls_layout = QHBoxLayout(controls)

        controls_layout.setContentsMargins(
            24, 10, 24, 10
        )

        controls_layout.setSpacing(10)

        # container
        controls_layout.addWidget(
            self._label("Container:")
        )

        self.container_combo = QComboBox()

        self.container_combo.setMinimumWidth(350)

        self.container_combo.setStyleSheet(
            self._combo_style()
        )

        self.container_combo.currentIndexChanged.connect(
            self._on_container_changed
        )

        controls_layout.addWidget(
            self.container_combo
        )

        # shell
        controls_layout.addWidget(
            self._label("Shell:")
        )

        self.shell_combo = QComboBox()

        self.shell_combo.addItems([
            "/bin/bash",
            "/bin/sh",
            "/bin/zsh",
        ])

        self.shell_combo.setStyleSheet(
            self._combo_style()
        )

        controls_layout.addWidget(
            self.shell_combo
        )

        # user
        controls_layout.addWidget(
            self._label("User:")
        )

        self.user_combo = QComboBox()

        self.user_combo.addItems([
            "root",
            "(padrão)",
        ])

        self.user_combo.setStyleSheet(
            self._combo_style()
        )

        controls_layout.addWidget(
            self.user_combo
        )

        controls_layout.addStretch()

        # atualizar
        self.refresh_button = QPushButton(
            "↻ Atualizar"
        )

        self.refresh_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.refresh_button.setStyleSheet(
            self._secondary_button_style()
        )

        self.refresh_button.clicked.connect(
            self.load_containers
        )

        controls_layout.addWidget(
            self.refresh_button
        )

        # abrir terminal
        self.open_button = QPushButton(
            "▶ Abrir Terminal"
        )

        self.open_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.open_button.setStyleSheet(
            self._primary_button_style()
        )

        self.open_button.clicked.connect(
            self.open_terminal
        )

        controls_layout.addWidget(
            self.open_button
        )

        root.addWidget(controls)

        # =================================================
        # INFO
        # =================================================
        self.info = QTextEdit()

        self.info.setReadOnly(True)

        self.info.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.info.setStyleSheet(f"""
            QTextEdit {{
                background-color: {TERM_BG};
                color: {TERM_FG};
                border: none;
                padding: 18px;
                font-family: Consolas;
                font-size: 13px;
            }}
        """)

        self.info.setText(
            "Docker Terminal\n\n"
            "Selecione um container e clique em "
            "'Abrir Terminal'.\n\n"
            "O aplicativo abrirá um terminal REAL "
            "do sistema operacional.\n\n"
            "Dicas:\n"
            "- Alpine usa /bin/sh\n"
            "- Ubuntu usa /bin/bash\n"
            "- Debian usa /bin/bash\n"
        )

        root.addWidget(
            self.info,
            stretch=1
        )

        # =================================================
        # FOOTER
        # =================================================
        footer = QFrame()

        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {BG2};
                border-top: 1px solid {BORDER};
            }}
        """)

        footer_layout = QHBoxLayout(footer)

        footer_layout.setContentsMargins(
            24, 8, 24, 8
        )

        footer_text = QLabel(
            "Windows → CMD | Linux → Terminal padrão | macOS → Terminal.app"
        )

        footer_text.setStyleSheet(
            f"color: {TEXT_DIM};"
        )

        footer_layout.addWidget(
            footer_text
        )

        footer_layout.addStretch()

        root.addWidget(footer)

    # =====================================================
    # LABEL
    # =====================================================
    def _label(self, text):

        label = QLabel(text)

        label.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 12px;
        """)

        return label

    # =====================================================
    # COMBO STYLE
    # =====================================================
    def _combo_style(self):

        return f"""
            QComboBox {{
                background-color: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {BG2};
                color: {TEXT};
                selection-background-color: {ACCENT};
                border: 1px solid {BORDER};
            }}
        """

    # =====================================================
    # PRIMARY BUTTON
    # =====================================================
    def _primary_button_style(self):

        return f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: bold;
            }}

            QPushButton:hover {{
                background-color: #79c0ff;
            }}
        """

    # =====================================================
    # SECONDARY BUTTON
    # =====================================================
    def _secondary_button_style(self):

        return f"""
            QPushButton {{
                background-color: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 7px 14px;
            }}

            QPushButton:hover {{
                background-color: {BORDER};
            }}
        """

    # =====================================================
    # LOAD CONTAINERS
    # =====================================================
    def load_containers(self):

        self.container_combo.clear()

        self.containers.clear()

        try:

            client = GrpcClient()

            containers = client.list_containers()

        except Exception as error:

            self.container_combo.addItem(
                f"Erro: {error}"
            )

            self.open_button.setEnabled(False)

            return

        running = [
            c for c in containers
            if c.get("status") == "running"
        ]

        stopped = [
            c for c in containers
            if c.get("status") != "running"
        ]

        ordered = running + stopped

        for container in ordered:

            status = container.get(
                "status",
                "?"
            )

            icon = (
                "●"
                if status == "running"
                else "○"
            )

            label = (
                f"{icon} "
                f"{container.get('name')} "
                f"({container.get('id')}) "
                f"[{status}]"
            )

            self.container_combo.addItem(
                label
            )

            self.containers.append(
                container
            )

        if not self.containers:

            self.container_combo.addItem(
                "Nenhum container encontrado"
            )

            self.open_button.setEnabled(False)

            return

        self._on_container_changed(0)

    # =====================================================
    # CONTAINER CHANGED
    # =====================================================
    def _on_container_changed(self, index):

        if not self.containers:

            self.open_button.setEnabled(False)

            return

        if index < 0:

            self.open_button.setEnabled(False)

            return

        if index >= len(self.containers):

            self.open_button.setEnabled(False)

            return

        container = self.containers[index]

        is_running = (
            container.get("status")
            == "running"
        )

        self.open_button.setEnabled(
            is_running
        )

    # =====================================================
    # OPEN TERMINAL
    # =====================================================
    def open_terminal(self):

        index = self.container_combo.currentIndex()

        if index < 0:
            return

        if index >= len(self.containers):
            return

        container = self.containers[index]

        if container.get("status") != "running":

            QMessageBox.warning(
                self,
                "Container parado",
                "Inicie o container antes de abrir o terminal."
            )

            return

        container_id = container.get("id")

        shell = self.shell_combo.currentText()

        user_selected = self.user_combo.currentText()

        user = (
            None
            if user_selected == "(padrão)"
            else user_selected
        )

        system_name = platform.system().lower()

        docker_command = self._build_command(
            container_id=container_id,
            shell=shell,
            user=user,
            system_name=system_name
        )

        success = False

        # =================================================
        # WINDOWS
        # =================================================
        if system_name == "windows":

            command = (
                f'start cmd /k "{docker_command}"'
            )

            result = QProcess.startDetached(
                "cmd.exe",
                ["/c", command]
            )

            success = result[0] if isinstance(result, tuple) else result

        # =================================================
        # LINUX
        # =================================================
        elif system_name == "linux":

            terminals = [

                (
                    "x-terminal-emulator",
                    [
                        "-e",
                        "bash",
                        "-lc",
                        docker_command
                    ]
                ),

                (
                    "gnome-terminal",
                    [
                        "--",
                        "bash",
                        "-lc",
                        docker_command
                    ]
                ),

                (
                    "konsole",
                    [
                        "-e",
                        "bash",
                        "-lc",
                        docker_command
                    ]
                ),

                (
                    "xfce4-terminal",
                    [
                        "-e",
                        f"bash -lc {shlex.quote(docker_command)}"
                    ]
                ),

                (
                    "xterm",
                    [
                        "-e",
                        "bash",
                        "-lc",
                        docker_command
                    ]
                ),
            ]

            for program, args in terminals:

                if shutil.which(program):

                    result = QProcess.startDetached(
                        program,
                        args
                    )

                    success = result[0] if isinstance(result, tuple) else result

                    if success:
                        break

        # =================================================
        # MACOS
        # =================================================
        elif system_name == "darwin":

            escaped = docker_command.replace(
                "\\",
                "\\\\"
            ).replace(
                '"',
                '\\"'
            )

            script = f'''
            tell application "Terminal"
                activate
                do script "{escaped}"
            end tell
            '''

            result = QProcess.startDetached(
                "osascript",
                [
                    "-e",
                    script
                ]
            )

            success = result[0] if isinstance(result, tuple) else result

        # =================================================
        # ERROR
        # =================================================
        if not success:

            QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível abrir o terminal.\n\n"
                "Verifique:\n"
                "- Docker instalado\n"
                "- Docker Desktop aberto\n"
                "- Terminal disponível no sistema"
            )

            return

        self.info.append(
            f"\nTerminal aberto:\n{docker_command}\n"
        )
    # =====================================================
    # BUILD COMMAND
    # =====================================================
    def _build_command(
        self,
        container_id,
        shell,
        user,
        system_name
    ):

        parts = [
            "docker",
            "exec",
            "-it"
        ]

        if user:

            parts.extend([
                "-u",
                user
            ])

        parts.extend([
            container_id,
            shell
        ])

        # windows
        if system_name == "windows":

            command = (
                f'docker exec -it '
            )

            if user:
                command += f'-u {user} '

            command += f'{container_id} {shell}'

            result = QProcess.startDetached(
                "cmd.exe",
                [
                    "/k",
                    command
                ]
            )

            success = result[0] if isinstance(result, tuple) else result

        # linux/mac
        return " ".join(
            shlex.quote(str(part))
            for part in parts
        )