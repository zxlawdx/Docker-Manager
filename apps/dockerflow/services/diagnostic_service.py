"""Read-only, opt-in network diagnostic from an existing running container."""
from .docker_service import docker_service


def connectivity(source, target):
    if not source or not target or source == target:
        raise ValueError("Selecione dois containers diferentes")
    containers = docker_service.client.containers
    left, right = containers.get(source), containers.get(target)
    left.reload()
    right.reload()
    left_nets = set((left.attrs.get("NetworkSettings", {}).get("Networks") or {}).keys())
    right_nets = set((right.attrs.get("NetworkSettings", {}).get("Networks") or {}).keys())
    shared = sorted(left_nets & right_nets)
    result = {"source": left.name, "target": right.name, "shared_networks": shared,
              "probe": "not_run", "output": ""}
    if not shared:
        result["explanation"] = "Não há rede compartilhada; isso não prova ausência de qualquer rota alternativa."
        return result
    # A lista de argumentos evita comandos de shell e interpolação de entradas.
    # A verificação por nome pode falhar em imagens sem getent/ping.
    for cmd in (["getent", "hosts", right.name], ["ping", "-c", "1", "-W", "2", right.name]):
        try:
            code, output = left.exec_run(cmd, demux=False)
            if code == 0:
                result.update(probe="success", output=output.decode("utf-8", "replace")[:1500])
                break
            result.update(probe="inconclusive", output=output.decode("utf-8", "replace")[:1500])
        except Exception as exc:
            result.update(probe="unavailable", output=type(exc).__name__)
    return result


def disk_usage():
    """API do daemon fornece espaço recuperável, sem cálculos incorretos por tag."""
    raw = docker_service.client.api.df()
    return {"images": [{"size": x.get("Size", 0), "shared": x.get("SharedSize", 0),
                         "tags": x.get("RepoTags") or []} for x in raw.get("Images") or []],
            "volumes": [{"name": x.get("Name"), "usage": x.get("UsageData") or {}}
                        for x in raw.get("Volumes") or []],
            "layers_size": raw.get("LayersSize", 0)}


def service_probe(source, target, protocol="dns", port=None):
    """Teste entre dois containers do Docker; não executa shell nem vasculha redes externas."""
    if protocol not in ("dns", "tcp", "http"):
        raise ValueError("Selecione DNS, TCP ou HTTP")
    if not isinstance(source, str) or not isinstance(target, str) or not source or not target or source == target:
        raise ValueError("Selecione dois containers distintos")
    p = None
    if protocol != "dns":
        try:
            p = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError("Porta TCP/HTTP inválida") from exc
        if not 1 <= p <= 65535:
            raise ValueError("Porta fora do intervalo")
    containers = docker_service.client.containers
    left, right = containers.get(source), containers.get(target)
    left.reload()
    right.reload()
    if left.status != "running" or right.status != "running":
        raise ValueError("Os dois containers devem estar em execução")
    left_nets = set((left.attrs.get("NetworkSettings", {}).get("Networks") or {}).keys())
    right_nets = set((right.attrs.get("NetworkSettings", {}).get("Networks") or {}).keys())
    shared = sorted(left_nets & right_nets)
    result = {"source": left.name, "target": right.name, "protocol": protocol,
              "port": p, "shared_networks": shared, "status": "not_run", "output": ""}
    if not shared:
        result["explanation"] = ("Sem rede compartilhada; não executado. "
                                 "Isso não prova a ausência de rotas alternativas.")
        return result
    if protocol == "dns":
        attempts = [["getent", "hosts", right.name], ["nslookup", right.name]]
    elif protocol == "tcp":
        attempts = [["nc", "-z", "-w", "3", right.name, str(p)]]
    else:
        import re
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", right.name):
            raise ValueError("Nome de container incompatível com URL HTTP")
        attempts = [["wget", "-q", "--server-response", "--spider", "--timeout=4",
                     "http://" + right.name + ":" + str(p) + "/"]]
    for command in attempts:
        try:
            code, output = left.exec_run(command, demux=False)
            result["output"] = (output or b"").decode("utf-8", "replace")[:1200]
            result["tool"] = command[0]
            result["status"] = "success" if code == 0 else (
                "inconclusive" if protocol == "http" else "failed")
            result["explanation"] = ("Teste concluído na ferramenta do container."
                                     if code == 0 else
                                     "Falha do comando não comprova ausência de rota ou serviço.")
            return result
        except Exception:
            # Busybox/scratch frequentemente não traz nc/wget/getent.
            result["status"] = "unavailable"
            result["explanation"] = ("Ferramenta não disponível neste container; "
                                     "não é possível inferir o estado da conexão.")
    return result
