"""Conversão do desenho em YAML Compose; nunca aplica nada ao Docker implicitamente."""
import re
import yaml

def slug(value, prefix):
    cleaned = re.sub(r"[^a-z0-9_-]", "-", str(value).lower()).strip("-_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = prefix + "-" + cleaned
    return cleaned[:52]

def to_compose(graph):
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    services, networks = {}, {}
    names = {}
    for n in nodes.values():
        if n.get("kind") == "network":
            key = slug(n.get("name") or n["id"], "network")
            if key in networks:
                raise ValueError("Nomes de rede duplicados")
            names[n["id"]] = key
            # Rede desenhada marcada como existente: Compose não deve recriá-la.
            networks[key] = ({"external": True, "name": n["name"]}
                             if n.get("existing") else {"driver": "bridge"})
    for n in nodes.values():
        if n.get("kind") != "container":
            continue
        key = slug(n.get("name") or n["id"], "service")
        image = n.get("image")
        if not image:
            raise ValueError("Informe a imagem do contêiner " + key)
        if key in services:
            raise ValueError("Nomes de serviço duplicados")
        services[key] = {"image": image}
        names[n["id"]] = key
    if not services:
        raise ValueError("Desenhe ao menos um contêiner")
    for e in graph.get("edges", []):
        a, b = nodes.get(e.get("source")), nodes.get(e.get("target"))
        if not a or not b:
            continue
        if {a.get("kind"), b.get("kind")} != {"container", "network"}:
            continue
        c = a if a["kind"] == "container" else b
        n = b if a["kind"] == "container" else a
        svc = services[names[c["id"]]]
        svc.setdefault("networks", [])
        if names[n["id"]] not in svc["networks"]:
            svc["networks"].append(names[n["id"]])
    return yaml.safe_dump({"services": services, "networks": networks},
                          sort_keys=False, allow_unicode=True)
