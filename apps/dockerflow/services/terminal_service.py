"""Sessões PTY Docker. I/O via HTTP polling para WebView (sem websocket/gRPC)."""
from collections import deque
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4
from docker.errors import DockerException
from .docker_service import docker_service


class TerminalService:
    def __init__(self):
        self.sessions = {}
        self.lock = Lock()

    def open(self, container_id, shell="/bin/sh", user=""):
        if shell not in ("/bin/sh", "/bin/bash", "/bin/ash"):
            raise ValueError("Shell não permitido")
        container = docker_service.client.containers.get(container_id)
        if container.status != "running":
            raise ValueError("Inicie o contêiner para abrir o terminal")
        with self.lock:
            if len(self.sessions) >= 4:
                raise ValueError("Feche outro terminal antes de criar uma sessão")
        api = docker_service.client.api
        params = {"container": container.id, "cmd": [shell], "stdin": True,
                  "tty": True, "stdout": True, "stderr": True, "environment": {"TERM": "dumb"}}
        if user in ("root", ""):
            if user:
                params["user"] = user
        else:
            raise ValueError("Usuário inválido")
        eid = api.exec_create(**params)["Id"]
        sock = api.exec_start(eid, socket=True, tty=True)
        sid = str(uuid4())
        state = {"socket": sock, "chunks": deque(), "alive": True, "last": monotonic()}
        with self.lock:
            self.sessions[sid] = state

        def reader():
            try:
                while state["alive"]:
                    chunk = sock._sock.recv(16384)
                    if not chunk:
                        break
                    with self.lock:
                        state["chunks"].append(chunk.decode("utf-8", "replace"))
                        while len(state["chunks"]) > 200:
                            state["chunks"].popleft()
            except (OSError, DockerException):
                pass
            finally:
                with self.lock:
                    state["alive"] = False

        Thread(target=reader, daemon=True).start()
        return {"session": sid, "shell": shell}

    def poll(self, sid):
        with self.lock:
            state = self.sessions.get(sid)
            if state is None:
                raise ValueError("Sessão indisponível")
            state["last"] = monotonic()
            output = "".join(state["chunks"])
            state["chunks"].clear()
            return {"output": output, "alive": state["alive"]}

    def send(self, sid, data):
        if not isinstance(data, str) or len(data) > 8192:
            raise ValueError("Entrada inválida")
        with self.lock:
            state = self.sessions.get(sid)
            if not state or not state["alive"]:
                raise ValueError("Terminal encerrado")
            state["last"] = monotonic()
            socket = state["socket"]
        socket._sock.sendall(data.encode("utf-8"))
        return {"ok": True}

    def close(self, sid):
        with self.lock:
            state = self.sessions.pop(sid, None)
        if state:
            state["alive"] = False
            try:
                state["socket"].close()
            except OSError:
                pass
        return {"ok": True}

terminal_service = TerminalService()
