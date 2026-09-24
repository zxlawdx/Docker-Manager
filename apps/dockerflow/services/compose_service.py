"""Workspace local para Docker Compose. CLI chamada sem shell nem path externo."""
from pathlib import Path
import os
import re
import subprocess
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

def save(name, content):
    _validate(content)
    folder = _project(name)
    folder.mkdir(parents=True, exist_ok=True)
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
    command = ["docker", "compose", "-p", name, "-f", str(target)]
    command += {"validate": ["config", "-q"], "up": ["up", "-d"],
                "down": ["down"], "ps": ["ps"]}[action]
    try:
        result = subprocess.run(command, cwd=target.parent, capture_output=True,
                                text=True, timeout=180, check=False,
                                env=os.environ.copy())
    except FileNotFoundError as exc:
        raise ValueError("Docker Compose CLI não encontrado no PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("A ação excedeu 180 segundos; confira estado Docker") from exc
    return {"ok": result.returncode == 0, "code": result.returncode,
            "output": (result.stdout + "\n" + result.stderr)[-40000:]}

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
        ignore.write_text(".git\\n.env\\n*.env\\ncompose.yml\\ncompose.yaml\\n", encoding="utf-8")
    return {"ok": True, "folder": str(folder)}
