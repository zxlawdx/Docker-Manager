"""Workspace local para Docker Compose. CLI chamada sem shell nem path externo."""
from pathlib import Path
import json
import os
import re
import stat
import subprocess
import tempfile
import yaml
from platformdirs import user_data_dir

BASE = Path(user_data_dir("DockerFlow", "zxlawdx")) / "projects"
BASE.mkdir(parents=True, exist_ok=True)

def _project(name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", name):
        raise ValueError("Nome do projeto: minúsculas, dígitos, _ e - (começa com letra).")
    return BASE / name

def _validate(content):
    if not isinstance(content, str) or not 0 < len(content) < 262144:
        raise ValueError("YAML vazio ou muito grande")
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("services"), dict):
        raise ValueError("O Compose precisa de uma seção services válida")
    return parsed

# Cofre local por projeto. Protege permissões no disco; não é keyring.
# Nenhum endpoint pode ler/devolver o valor salvo: status só informa sua presença.
KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
REFERENCE = re.compile(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[?+-]|[?+-])?[^}]*\}")
VAULT = ".dockerflow-env.json"


def _private_dir(name, create=False):
    folder = _project(name)
    if folder.is_symlink():
        raise PermissionError("Workspace simbólico não permitido para segredos.")
    if create:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix":
            folder.chmod(0o700)
    if folder.exists() and not folder.is_dir():
        raise ValueError("Workspace inválido")
    return folder


def _read_private(name):
    target = _private_dir(name) / VAULT
    try:
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return {}
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or (
            hasattr(os, "getuid") and meta.st_uid != os.getuid()
        ):
            raise PermissionError("Arquivo de variáveis não é privado.")
        if os.name == "posix" and meta.st_mode & 0o077:
            raise PermissionError("Arquivo de variáveis não está protegido (exige 0600).")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            values = json.load(stream)
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(values, dict) or any(
        not isinstance(k, str) or not KEY.fullmatch(k) or not isinstance(v, str)
        for k, v in values.items()
    ):
        raise ValueError("Cofre de variáveis inválido.")
    return values


def _write_private(name, values):
    folder = _private_dir(name, create=True)
    fd, temporary = tempfile.mkstemp(prefix=".dockerflow-env-", dir=folder)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(values, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, folder / VAULT)
    finally:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(temporary):
            os.unlink(temporary)


def variables_status(name, content=""):
    saved = _read_private(name)
    if not isinstance(content, str) or len(content) > 262144:
        raise ValueError("YAML grande demais")
    used = set(REFERENCE.findall(content))
    return {
        "project": name,
        "variables": [{
            "name": key,
            "saved": key in saved,
            "from_system": key not in saved and bool(os.environ.get(key)),
            "used_by_yaml": key in used,
        } for key in sorted(used | set(saved))],
        "storage": "Cofre JSON local do projeto; chmod 0600 no Linux."
    }


def set_variable(name, key, value):
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError("Nome de variável inválido.")
    if not isinstance(value, str) or not value or len(value) > 4096 or any(
        c in value for c in "\0\r\n"
    ):
        raise ValueError("Valor obrigatório: máximo de 4096 caracteres sem quebras de linha.")
    values = _read_private(name)
    if len(values) >= 100 and key not in values:
        raise ValueError("Máximo de 100 variáveis por projeto.")
    values[key] = value
    _write_private(name, values)
    return {"ok": True, "name": key, "saved": True}


def delete_variable(name, key):
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError("Nome de variável inválido.")
    values = _read_private(name)
    if key in values:
        del values[key]
        _write_private(name, values)
    return {"ok": True, "name": key}


def _redact_output(output, values):
    # Não ecoar segredos em resultados CLI, inclusive falhas de interpolação.
    for value in sorted(set(values.values()), key=len, reverse=True):
        if value:
            output = output.replace(value, "[SEGREDO OCULTADO]")
    return output


def save(name, content):
    _validate(content)
    folder = _private_dir(name, create=True)
    target = folder / "compose.yml"
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "file": str(target)}

def load(name):
    target = _project(name) / "compose.yml"
    if not target.is_file():
        raise ValueError("Projeto inexistente")
    dockerfile = target.parent / "Dockerfile"
    return {"name": name, "content": target.read_text(encoding="utf-8"),
            "dockerfile": dockerfile.read_text(encoding="utf-8") if dockerfile.is_file() else ""}

def projects():
    return sorted([p.name for p in BASE.iterdir()
                   if p.is_dir() and (p / "compose.yml").is_file()])

def execute(name, action, content=None):
    if action not in ("validate", "up", "down", "ps"):
        raise ValueError("Ação Compose inválida")
    if content is not None:
        save(name, content)
    target = _project(name) / "compose.yml"
    if not target.is_file():
        raise ValueError("Salve o YAML antes de executar")
    secrets = _read_private(name)
    command = ["docker", "compose", "-p", name, "-f", str(target)]
    command += {"validate": ["config", "-q"], "up": ["up", "-d"],
                "down": ["down"], "ps": ["ps"]}[action]
    try:
        result = subprocess.run(command, cwd=target.parent, capture_output=True,
                                text=True, timeout=180, check=False,
                                env={**os.environ.copy(), **secrets})
    except FileNotFoundError as exc:
        raise ValueError("Docker Compose CLI não encontrado no PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("A ação excedeu 180 segundos; confira estado Docker") from exc
    return {"ok": result.returncode == 0, "code": result.returncode,
            "output": _redact_output((result.stdout + "\n" + result.stderr)[-40000:], secrets)}

def save_dockerfile(name, content):
    """Editor Dockerfile é persistido no mesmo workspace; build exige ação explícita."""
    if not isinstance(content, str) or not 0 < len(content) <= 65536:
        raise ValueError("Dockerfile vazio ou acima do limite de 64 KiB")
    folder = _project(name)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "Dockerfile"
    target.write_text(content, encoding="utf-8")
    ignore = folder / ".dockerignore"
    if not ignore.exists():
        ignore.write_text(chr(10).join([".git", ".env", "*.env", "compose.yml", "compose.yaml", ""]), encoding="utf-8")
    return {"ok": True, "folder": str(folder)}
