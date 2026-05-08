from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from grpc_client import GrpcClient

class CreateContainerPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        # Layout principal com margens generosas (padrão da doc)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título da Página
        title = QLabel("🚀 Criar Novo Container")
        title.setObjectName("PageTitle") # Usa o estilo CSS do projeto
        layout.addWidget(title)

        # Container para o formulário (opcional, para organização)
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(10)

        # Campo: Imagem
        lbl_image = QLabel("Imagem Docker (ex: nginx, alpine, postgres):")
        self.input_image = QLineEdit()
        self.input_image.setPlaceholderText("Digite o nome da imagem...")
        
        # Campo: Nome do Container
        lbl_name = QLabel("Nome do Container (opcional):")
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Digite um nome para o container...")

        # Adicionando ao layout do formulário
        form_layout.addWidget(lbl_image)
        form_layout.addWidget(self.input_image)
        form_layout.addWidget(lbl_name)
        form_layout.addWidget(self.input_name)
        
        layout.addWidget(form_frame)

        # Botão de Ação
        self.btn_create = QPushButton("Criar Container")
        self.btn_create.setObjectName("PrimaryButton") # Estilo verde definido no CSS
        self.btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create.clicked.connect(self._handle_create)
        
        layout.addWidget(self.btn_create)
        
        # Estica o espaço abaixo para manter tudo no topo
        layout.addStretch()

    def _handle_create(self):
        image = self.input_image.text().strip()
        name = self.input_name.text().strip()

        if not image:
            QMessageBox.warning(self, "Campo Obrigatório", "Você precisa informar o nome de uma imagem.")
            return

        # Desabilita o botão para evitar cliques duplos
        self.btn_create.setEnabled(False)
        self.btn_create.setText("Criando... aguarde")

        try:
            client = GrpcClient()
            # Chama a função que você acabou de adicionar no grpc_client.py
            success, message = client.create_container(image, name)

            if success:
                QMessageBox.information(self, "Sucesso", f"O container foi criado!\n{message}")
                self.input_image.clear()
                self.input_name.clear()
            else:
                QMessageBox.critical(self, "Erro ao Criar", f"Ocorreu um erro:\n{message}")
        
        except Exception as e:
            QMessageBox.critical(self, "Erro de Conexão", f"Não foi possível falar com o servidor:\n{str(e)}")
        
        finally:
            self.btn_create.setEnabled(True)
            self.btn_create.setText("Criar Container")