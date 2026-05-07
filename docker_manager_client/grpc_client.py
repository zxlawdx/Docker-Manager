"""
grpc_client.py - Centraliza toda a comunicação com o backend gRPC.

Ao invés de chamar o stub diretamente nas páginas, você usa esta classe.
Isso facilita: trocar o backend, mockar nos testes, tratar erros num só lugar.
"""

import sys
import os

# Ajusta o path para encontrar os arquivos gerados pelo protoc
sys.path.insert(0, os.path.abspath("../grpc_server"))

import grpc

try:
    import docker_manager_pb2      as pb2
    import docker_manager_pb2_grpc as pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    print("[AVISO] Arquivos gRPC não encontrados. Usando dados de exemplo.")


class GrpcClient:
    """
    Cliente gRPC para o DockerManager.

    Uso:
        client = GrpcClient()
        containers = client.list_containers()
    """

    HOST = "localhost"
    PORT = 50051

    def __init__(self):
        if GRPC_AVAILABLE:
            self._channel = grpc.insecure_channel(f"{self.HOST}:{self.PORT}")
            self._stub    = pb2_grpc.DockerManagerStub(self._channel)
        else:
            self._channel = None
            self._stub    = None

    # ── Containers ───────────────────────────────────────────────────────────

    def list_containers(self) -> list[dict]:
        """Retorna lista de dicts com id, name, image, status, ports."""
        if not GRPC_AVAILABLE:
            return _mock_containers()

        response = self._stub.ListContainers(pb2.Empty())
        result = []
        for c in response.containers:
            result.append({
                "id":     c.id,
                "name":   c.name,
                "image":  getattr(c, "image",  ""),
                "status": c.status,
                "ports":  getattr(c, "ports",  ""),
            })
        return result

    def start_container(self, container_id: str) -> tuple[bool, str]:
        """Inicia um container. Retorna (sucesso, mensagem)."""
        if not GRPC_AVAILABLE:
            return True, "OK (mock)"

        response = self._stub.StartContainer(pb2.ContainerRequest(id=container_id))
        return response.success, getattr(response, "message", "")

    def stop_container(self, container_id: str) -> tuple[bool, str]:
        """Para um container. Retorna (sucesso, mensagem)."""
        if not GRPC_AVAILABLE:
            return True, "OK (mock)"

        response = self._stub.StopContainer(pb2.ContainerRequest(id=container_id))
        return response.success, getattr(response, "message", "")

    def remove_container(self, container_id: str) -> tuple[bool, str]:
        """Remove um container. Retorna (sucesso, mensagem)."""
        if not GRPC_AVAILABLE:
            return True, "OK (mock)"

        response = self._stub.RemoveContainer(pb2.ContainerRequest(id=container_id))
        return response.success, getattr(response, "message", "")

    # ── Imagens ──────────────────────────────────────────────────────────────

    def list_images(self) -> list[dict]:
        """Retorna lista de dicts com id, repo, tag, size, created."""
        if not GRPC_AVAILABLE:
            return _mock_images()

        response = self._stub.ListImages(pb2.Empty())

        result = []

        for img in response.images:
            full_tag = getattr(img, "tag", "<none>:<none>")

            if ":" in full_tag:
                repo, tag = full_tag.rsplit(":", 1)
            else:
                repo = full_tag
                tag = "<none>"

            result.append({
                "id": getattr(img, "short_id", img.id),
                "repo": repo,
                "tag": tag,
                "size": getattr(img, "disk_usage", ""),
                "created": getattr(img, "created", ""),
            })

        return result


# ── Dados de exemplo (usados quando o gRPC não está disponível) ──────────────

def _mock_containers() -> list[dict]:
    return [
        {"id": "abc123def456",  "name": "nginx-web",     "image": "nginx:latest",    "status": "running", "ports": "0.0.0.0:80->80/tcp"},
        {"id": "def456abc789",  "name": "postgres-db",   "image": "postgres:15",     "status": "running", "ports": "5432/tcp"},
        {"id": "789xyz000aaa",  "name": "redis-cache",   "image": "redis:alpine",    "status": "exited",  "ports": ""},
        {"id": "111bbb222ccc",  "name": "my-api",        "image": "myapp:v2.1",      "status": "running", "ports": "0.0.0.0:3000->3000/tcp"},
    ]

def _mock_images() -> list[dict]:
    return [
        {"id": "sha256:aaa111", "repo": "nginx",    "tag": "latest",  "size": "142 MB", "created": "2 days ago"},
        {"id": "sha256:bbb222", "repo": "postgres", "tag": "15",      "size": "379 MB", "created": "1 week ago"},
        {"id": "sha256:ccc333", "repo": "redis",    "tag": "alpine",  "size": "29 MB",  "created": "3 days ago"},
        {"id": "sha256:ddd444", "repo": "myapp",    "tag": "v2.1",    "size": "210 MB", "created": "5 hours ago"},
    ]
