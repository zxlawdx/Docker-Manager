"""Operações de risco: somente Docker local e autorização polkit do SO.

Nunca solicite senha sudo no HTML nem execute shell recebido do navegador.
A remoção em massa requer preview do estado atual + frase explícita + pkexec.
"""
import hashlib
import hmac
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading

import docker
from .security_service import TOKEN


SOCKET = "/var/run/docker.sock"
PHRASE = "APAGAR TODOS"
_GATE = threading.Lock()


class AdminService:
    def __init__(self, factory=None, runner=None, which=None, socket=SOCKET):
        self._factory = factory or (lambda: docker.DockerClient(base_url="unix://" + socket))
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self._socket = socket

    def _check_local(self):
        if not sys.platform.startswith("linux"):
            raise PermissionError("A confirmação por polkit só está disponível no Linux.")
        if os.geteuid() == 0:
            raise PermissionError("Abra o DockerFlow como usuário normal para exigir a autorização do SO.")
        if os.environ.get("DOCKER_HOST", "") not in ("", "unix://" + self._socket):
            raise PermissionError("Esta ação só admite o Docker Engine local, não hosts remotos ou rootless.")
        if os.environ.get("DOCKER_CONTEXT", "") not in ("", "default"):
            raise PermissionError("Selecione o contexto Docker local antes de usar o painel administrador.")
        path = Path(self._socket)
        if not path.exists() or not stat.S_ISSOCK(path.stat().st_mode):
            raise PermissionError("Socket Docker local padrão não encontrado.")

    def _list(self):
        self._check_local()
        client = self._factory()
        try:
            rows = []
            for item in client.containers.list(all=True):
                ident = str(item.id)
                if not re.fullmatch(r"[a-fA-F0-9]{12,64}", ident):
                    raise ValueError("Identidade Docker inesperada: operação recusada.")
                rows.append((ident.lower(), str(item.name)[:120]))
            if len(rows) > 1000:
                raise ValueError("Mais de 1000 containers; divisão manual obrigatória por segurança.")
            return sorted(rows)
        finally:
            client.close()

    def _fingerprint(self, rows):
        ids = ",".join(identifier for identifier, _ in rows)
        return hmac.new(TOKEN.encode("utf-8"), ids.encode("ascii"), hashlib.sha256).hexdigest()

    def preview(self):
        rows = self._list()
        return {
            "count": len(rows),
            "containers": [{"id": ident[:12], "name": name} for ident, name in rows[:100]],
            "truncated": len(rows) > 100,
            "fingerprint": self._fingerprint(rows),
            "scope": "unix://" + self._socket,
            "auth": "polkit (pkexec)",
            "warning": "Força a remoção dos containers em execução e parados. Volumes nomeados não são apagados.",
        }

    def _trusted_binary(self, name, allowed):
        raw = self._which(name)
        if not raw:
            raise PermissionError(name + " não encontrado. Instale o programa e agente polkit gráfico.")
        executable = Path(raw).resolve()
        if str(executable) not in allowed:
            raise PermissionError(name + " não está numa instalação de sistema confiável.")
        info = executable.stat()
        if info.st_uid != 0 or info.st_mode & stat.S_IWOTH or not info.st_mode & stat.S_IXUSR:
            raise PermissionError(name + " precisa ser executável do sistema pertencente ao root.")
        return str(executable)

    def remove_all(self, fingerprint, confirmation):
        if confirmation != PHRASE or not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("Confirmação ou prévia inválida.")
        if not _GATE.acquire(blocking=False):
            raise ValueError("Outra operação administrativa está em andamento.")
        try:
            rows = self._list()
            if not rows:
                return {"ok": True, "removed": 0, "remaining": 0,
                        "message": "Não há containers para remover."}
            if not hmac.compare_digest(self._fingerprint(rows), fingerprint):
                raise ValueError("A lista de containers mudou. Faça uma nova prévia e confirme novamente.")
            pkexec = self._trusted_binary("pkexec", {"/usr/bin/pkexec", "/bin/pkexec"})
            docker_bin = self._trusted_binary("docker", {"/usr/bin/docker", "/usr/local/bin/docker"})
            # A autorização aparece na interface gráfica do sistema, fora da WebView.
            # Não utilizamos shell nem transmitimos senhas ao backend.
            args = [pkexec, docker_bin, "--host", "unix://" + self._socket,
                    "container", "rm", "--force", "--"]
            args.extend(identifier for identifier, _ in rows)
            try:
                execution = self._runner(args, capture_output=True, text=True,
                                         timeout=180, check=False)
            except subprocess.TimeoutExpired:
                return {"ok": False, "removed": None, "remaining": None,
                        "message": "Autorização excedeu o tempo limite. Atualize a prévia para verificar o estado."}
            except OSError:
                return {"ok": False, "removed": None, "remaining": None,
                        "message": "Falha ao abrir a autorização do sistema. Configure um agente polkit gráfico."}
            try:
                remaining_rows = self._list()
            except Exception:
                return {"ok": False, "removed": None, "remaining": None,
                        "message": "Releitura do Docker falhou. Faça uma nova prévia antes de qualquer outra ação."}
            left = {ident for ident, _ in remaining_rows}
            removed = len([ident for ident, _ in rows if ident not in left])
            ok = execution.returncode == 0 and removed == len(rows)
            return {"ok": ok, "removed": removed, "remaining": len(remaining_rows),
                    "message": ("Remoção concluída; volumes nomeados preservados." if ok else
                                "Operação negada ou parcialmente concluída. Verifique o Docker antes de repetir.")}
        finally:
            _GATE.release()


admin_service = AdminService()
