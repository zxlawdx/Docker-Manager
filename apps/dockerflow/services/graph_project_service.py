"""Versioned, locally persisted DockerFlow topology documents.

Saved diagrams are untrusted drafts. Persistence is never proof that an ID
still belongs to the same real Docker resource.
"""
import json
import os
import re
import tempfile
from pathlib import Path
from platformdirs import user_data_dir

BASE = Path(user_data_dir("DockerFlow", "zxlawdx")) / "diagrams"
BASE.mkdir(parents=True, exist_ok=True)


def _path(name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,39}", name):
        raise ValueError("Nome: letras, números, _ ou -, começando com letra")
    return BASE / (name + ".json")


def validate(graph):
    if not isinstance(graph, dict) or graph.get("version") != 2:
        raise ValueError("Versão desconhecida do diagrama")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 150 or len(edges) > 350:
        raise ValueError("Diagrama acima do limite ou malformado")
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or node.get("kind") not in ("network", "container"):
            raise ValueError("Tipo de bloco inválido")
        key = node.get("id")
        if (not isinstance(key, str) or len(key) > 130 or key in ids or
                not isinstance(node.get("name"), str) or len(node["name"]) > 128 or
                not isinstance(node.get("x"), (int, float)) or
                not isinstance(node.get("y"), (int, float)) or
                abs(node["x"]) > 100000 or abs(node["y"]) > 100000):
            raise ValueError("Bloco duplicado ou inválido")
        ids.add(key)
    for edge in edges:
        if (not isinstance(edge, dict) or edge.get("source") not in ids or
                edge.get("target") not in ids or edge["source"] == edge["target"]):
            raise ValueError("Ligação inválida")
    payload = {"version": 2, "nodes": nodes, "edges": edges,
               "source_compose": graph.get("source_compose") or ""}
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 524288:
        raise ValueError("Documento excede 512 KiB")
    return payload


def save(name, graph):
    payload = validate(graph)
    target = _path(name)
    fd, temporary = tempfile.mkstemp(dir=BASE, prefix=".diagram-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(payload, writer, ensure_ascii=False, indent=2)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"ok": True, "name": name}


def load(name):
    target = _path(name)
    if not target.is_file():
        raise ValueError("Diagrama não encontrado")
    return validate(json.loads(target.read_text(encoding="utf-8")))


def projects():
    return sorted(path.stem for path in BASE.glob("*.json") if _path(path.stem).is_file())


def drift(graph, docker_service):
    """Comparação de estado, nunca altera o Docker Engine."""
    payload = validate(graph)
    actual_containers = {item["name"]: item for item in docker_service.containers()}
    actual_networks = {item["name"]: item for item in docker_service.networks()}
    planned_containers = {n["name"] for n in payload["nodes"] if n["kind"] == "container"}
    planned_networks = {n["name"] for n in payload["nodes"] if n["kind"] == "network"}
    missing = [{"kind": n["kind"], "name": n["name"]} for n in payload["nodes"]
               if n["name"] not in (actual_containers if n["kind"] == "container" else actual_networks)]
    unexpected = [{"kind": "container", "name": name} for name in actual_containers if name not in planned_containers]
    unexpected += [{"kind": "network", "name": name} for name in actual_networks if name not in planned_networks]
    by_id = {n["id"]: n for n in payload["nodes"]}
    disconnected = []
    for edge in payload["edges"]:
        source, target = by_id[edge["source"]], by_id[edge["target"]]
        if {source["kind"], target["kind"]} != {"container", "network"}:
            continue
        container = source if source["kind"] == "container" else target
        network = target if source["kind"] == "container" else source
        live = actual_containers.get(container["name"])
        if live and network["name"] not in live.get("networks", []):
            disconnected.append({"container": container["name"], "network": network["name"]})
    return {"missing": missing, "unexpected": unexpected,
            "missing_connections": disconnected,
            "note": "Comparação baseada em nomes; revise recursos recriados com o mesmo nome."}
