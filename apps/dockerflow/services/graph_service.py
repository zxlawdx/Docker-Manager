"""Conversão do desenho em YAML Compose; nunca aplica nada ao Docker implicitamente."""
import re
import json
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
            spec = ({"external": True, "name": n["name"]}
                    if n.get("existing") else {"driver": "bridge"})
            if not n.get("existing") and n.get("subnet"):
                import ipaddress
                subnet = ipaddress.ip_network(n["subnet"], strict=True)
                config = {"subnet": str(subnet)}
                if n.get("gateway"):
                    gateway = ipaddress.ip_address(n["gateway"])
                    if gateway not in subnet:
                        raise ValueError("Gateway fora da sub-rede de " + key)
                    config["gateway"] = str(gateway)
                spec["ipam"] = {"config": [config]}
            if n.get("internal") and not n.get("existing"):
                spec["internal"] = True
            networks[key] = spec
    for n in nodes.values():
        if n.get("kind") != "container":
            continue
        key = slug(n.get("name") or n["id"], "service")
        image = n.get("image")
        source = yaml.safe_load(graph.get("source_compose") or "{}") or {}
        original = (source.get("services") or {}).get(n.get("name")) or {}
        if not image and not original.get("build"):
            raise ValueError("Informe a imagem do contêiner " + key)
        if key in services:
            raise ValueError("Nomes de serviço duplicados")
        service = dict(original)
        if image:
            service["image"] = image
        if n.get("cpus") not in (None, ""):
            cpus = float(n["cpus"])
            if not 0.01 <= cpus <= 128:
                raise ValueError("CPU fora do intervalo em " + key)
            service["cpus"] = cpus
        if n.get("memory_mb") not in (None, ""):
            m = int(n["memory_mb"])
            if not 32 <= m <= 1048576:
                raise ValueError("Memória inválida no serviço " + key)
            service["mem_limit"] = str(m) + "m"
        if n.get("restart"):
            if n["restart"] not in ("no", "always", "unless-stopped", "on-failure"):
                raise ValueError("Política de restart desconhecida")
            service["restart"] = n["restart"]
        if n.get("read_only"):
            service["read_only"] = True
        host, inside = str(n.get("host_port") or "").strip(), str(n.get("container_port") or "").strip()
        if host or inside:
            if not (host.isdigit() and inside.isdigit()
                    and 1 <= int(host) <= 65535 and 1 <= int(inside) <= 65535):
                raise ValueError("Portas host/container inválidas no serviço " + key)
            service["ports"] = [host + ":" + inside]

        # Apenas variáveis declaradas no próprio diagrama.
        # Importar Docker não extrai Config.Env para evitar vazamento de segredos.
        raw_env = n.get("env_text") or "{}"
        if not isinstance(raw_env, str):
            raise ValueError("Variáveis em formato incorreto no serviço " + key)
        try:
            environment = json.loads(raw_env)
        except ValueError as exc:
            raise ValueError("JSON de ambiente inválido no serviço " + key) from exc
        if not isinstance(environment, dict):
            raise ValueError("O ambiente precisa ser objeto JSON em " + key)
        if environment:
            service["environment"] = {str(k): None if v is None else str(v)
                                      for k, v in environment.items()}
        services[key] = service
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
        if n.get("name") in ("host", "none"):
            raise ValueError("A rede padrão host/none exige network_mode e não pode ser exportada como rede bridge")
        svc = services[names[c["id"]]]
        svc.setdefault("networks", [])
        if names[n["id"]] not in svc["networks"]:
            svc["networks"].append(names[n["id"]])
    # Sem remover chaves Compose avançadas que o canvas ainda não representa.
    source = yaml.safe_load(graph.get("source_compose") or "{}") or {}
    if source and not isinstance(source, dict):
        raise ValueError("Fonte Compose inválida")
    doc = dict(source)
    doc["services"] = services
    doc["networks"] = networks
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def from_compose(content):
    """Compose -> rascunho visual. Não garante round-trip para campos desconhecidos."""
    if not isinstance(content, str) or len(content) > 262144:
        raise ValueError("Compose vazio ou acima do limite")
    doc = yaml.safe_load(content)
    if not isinstance(doc, dict) or not isinstance(doc.get("services"), dict):
        raise ValueError("Compose requer services")
    if len(doc["services"]) > 100:
        raise ValueError("Muitos serviços")
    nodes, edges, networks = [], [], {}
    declarations = doc.get("networks") or {}
    if not isinstance(declarations, dict):
        raise ValueError("Networks inválido")
    for i, (name, spec) in enumerate(declarations.items()):
        if not isinstance(spec, dict):
            spec = {}
        ident = "compose-network-" + str(i)
        networks[name] = ident
        nodes.append({"id": ident, "kind": "network",
                      "name": str(spec.get("name") or name),
                      "driver": spec.get("driver") or "bridge", "existing": False,
                      "x": 390, "y": 80 + i * 165})
    for i, (name, spec) in enumerate(doc["services"].items()):
        if not isinstance(spec, dict):
            raise ValueError("Serviço malformado: " + str(name))
        ident = "compose-service-" + str(i)
        item = {"id": ident, "kind": "container", "name": str(name),
                "image": str(spec.get("image") or ""),
                "existing": False, "x": 75, "y": 80 + i * 145,
                "env_text": json.dumps(spec.get("environment") if isinstance(spec.get("environment"), dict) else {})}
        ports = spec.get("ports") or []
        if ports and isinstance(ports[0], str):
            parts = ports[0].split(":")
            if len(parts) == 2 and all(x.isdigit() for x in parts):
                item["host_port"], item["container_port"] = parts
        nodes.append(item)
        connected = spec.get("networks") or []
        for network in (connected.keys() if isinstance(connected, dict) else connected):
            if network not in networks:
                ident_net = "compose-network-implicit-" + str(len(networks))
                networks[network] = ident_net
                nodes.append({"id": ident_net, "kind": "network", "name": network,
                              "driver": "bridge", "existing": False,
                              "x": 400, "y": 80 + len(networks) * 165})
            edges.append({"id": "compose-edge-" + str(len(edges)),
                          "source": networks[network], "target": ident,
                          "persisted": False})
    return {"version": 2, "nodes": nodes, "edges": edges, "source_compose": content}


def report(graph):
    """Documentação sem serializar variáveis de ambiente e credenciais."""
    nodes = {item["id"]: item for item in graph.get("nodes", [])}
    if len(nodes) > 150 or len(graph.get("edges", [])) > 350:
        raise ValueError("Diagrama grande demais")
    output = ["# DockerFlow · relatório de arquitetura", "",
              "Documentação descritiva gerada a partir do rascunho visual. Não prova conectividade real.",
              "", "## Elementos", "",
              "| Nome | Tipo | Imagem/driver |", "|---|---|---|"]
    for item in nodes.values():
        name = str(item.get("name", "")).replace("|", "\\|").replace(chr(10), " ")[:100]
        detail = str(item.get("image") if item.get("kind") == "container" else item.get("driver") or "")[:150]
        output.append("| " + name + " | " + str(item.get("kind")) +
                      " | " + detail.replace("|", "\\|") + " |")
    output.extend(["", "## Conexões desenhadas", ""])
    for edge in graph.get("edges", []):
        left, right = nodes.get(edge.get("source")), nodes.get(edge.get("target"))
        if left and right:
            output.append("- " + str(left.get("name", ""))[:80] + " ↔ " + str(right.get("name", ""))[:80])
    output.extend(["", "## Observações", "",
                   "- Revise portas, segredos, volumes, políticas de restart e limites de recursos na IDE.",
                   "- Esta representação não aplica mudanças ao Docker automaticamente."])
    return "\\n".join(output) + "\\n"
