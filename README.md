# 🐳 DockerFlow

**DockerFlow** é uma aplicação desktop para gerenciar containers e imagens Docker com uma interface gráfica moderna. Ele usa **gRPC** para a comunicação entre a interface (cliente) e o serviço que controla o Docker (servidor).

---

## 📋 Sumário

- [Como funciona](#como-funciona)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Como rodar](#como-rodar)
- [O que você pode fazer](#o-que-você-pode-fazer)
- [Como criar uma nova tela](#como-criar-uma-nova-tela)
- [Como criar uma nova função no backend](#como-criar-uma-nova-função-no-backend)
- [Tecnologias usadas](#tecnologias-usadas)

---

## Como funciona

O DockerFlow é dividido em duas partes que conversam entre si:

```
┌─────────────────────┐        gRPC (porta 50051)        ┌──────────────────────┐
│  Interface gráfica  │  ──────────────────────────────►  │  Servidor            │
│  (PyQt6)            │                                   │  (grpc_server)       │
│  docker_manager_    │  ◄──────────────────────────────  │                      │
│  client/            │        resposta Protobuf           │  Controla o Docker   │
└─────────────────────┘                                   └──────────────────────┘
```

1. Você abre a interface gráfica (cliente)
2. A interface faz uma chamada gRPC para o servidor
3. O servidor recebe o pedido, executa a ação no Docker e devolve a resposta
4. A interface exibe o resultado na tela

---

## Estrutura do projeto

```
docker_manager/
├── manage.py                        # Ponto de entrada: roda servidor, cliente ou ambos
├── requirements.txt                 # Dependências Python
│
├── grpc_server/                     # SERVIDOR — controla o Docker
│   ├── docker_manager.proto         # Contrato gRPC (define funções e tipos de dados)
│   ├── docker_manager_pb2.py        # Gerado automaticamente pelo protoc
│   ├── docker_manager_pb2_grpc.py   # Gerado automaticamente pelo protoc
│   ├── server.py                    # Lógica do servidor gRPC
│   └── url.py                       # Mapeamento de arquivos (usado pelo manage.py)
│
└── docker_manager_client/           # CLIENTE — interface gráfica
    ├── app.py                       # Ponto de entrada do cliente
    ├── main_window.py               # Janela principal + estilos globais
    ├── grpc_client.py               # Camada de comunicação com o servidor
    ├── containers_page.py           # Tela de gerenciamento de containers
    ├── images_page.py               # Tela de listagem de imagens
    ├── manage_widget.py             # Alternativa de inicialização da interface
    ├── url.py                       # Mapeamento de arquivos (usado pelo manage.py)
    └── models/
        └── container.py             # Modelo de dados de um container
```

---

## Requisitos

- Python **3.8+**
- Docker instalado e **em execução** na sua máquina
- pip atualizado

---

## Instalação

```bash
# 1. Clone ou extraia o projeto
cd docker_manager

# 2. (Recomendado) Crie um ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
# ou
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## Como rodar

O `manage.py` é o arquivo central que sobe tudo para você:

```bash
# Rodar servidor + cliente juntos (mais fácil)
python manage.py runall

# Rodar só o servidor gRPC
python manage.py runserver

# Rodar só o cliente (interface gráfica)
python manage.py runclient
```

O servidor precisa estar rodando antes do cliente. O `runall` já cuida disso automaticamente.

---

## O que você pode fazer

| Tela | Funcionalidade |
|------|---------------|
| **Containers** | Ver todos os containers, iniciar, parar e remover |
| **Imagens** | Ver todas as imagens Docker locais com tamanho e data |

---

## Como criar uma nova tela

1. Crie um arquivo na pasta `docker_manager_client/`, por exemplo `volumes_page.py`
2. Use este esqueleto como base:

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from grpc_client import GrpcClient

class VolumesPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.title = QLabel("📁 Volumes")
        self.title.setObjectName("PageTitle")
        layout.addWidget(self.title)

    def refresh(self):
        client = GrpcClient()
        # chame aqui a função do cliente gRPC
```

3. Registre a tela em `main_window.py`:

```python
from volumes_page import VolumesPage

# dentro de _build_ui(), adicione:
self._add_page("volumes", VolumesPage())

# e no nav_items da Sidebar, adicione:
("Volumes", "📁", "volumes"),
```

---

## Como criar uma nova função no backend

1. **Adicione o método no arquivo `.proto`** (`grpc_server/docker_manager.proto`):

```proto
service DockerManager {
  // ... funções existentes ...
  rpc ListVolumes (Empty) returns (VolumeList);
}

message VolumeInfo {
  string name = 1;
  string driver = 2;
}

message VolumeList {
  repeated VolumeInfo volumes = 1;
}
```

2. **Regere os arquivos automáticos** (dentro da pasta `grpc_server/`):

```bash
cd grpc_server
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. docker_manager.proto
```

3. **Implemente a função em `server.py`**:

```python
def ListVolumes(self, request, context):
    volumes = self.docker_client.volumes.list()
    response = pb2.VolumeList()
    for v in volumes:
        response.volumes.append(pb2.VolumeInfo(
            name=v.name,
            driver=v.attrs.get("Driver", "")
        ))
    return response
```

4. **Exponha a função em `grpc_client.py`**:

```python
def list_volumes(self) -> list[dict]:
    response = self._stub.ListVolumes(pb2.Empty())
    return [{"name": v.name, "driver": v.driver} for v in response.volumes]
```

---

## Tecnologias usadas

| Tecnologia | Para que serve |
|-----------|---------------|
| **PyQt6** | Interface gráfica desktop |
| **gRPC** | Comunicação entre cliente e servidor |
| **Protobuf** | Formato dos dados trocados via gRPC |
| **Docker SDK** | Controla o Docker via Python |
| **Python 3.12** | Linguagem principal do projeto |
