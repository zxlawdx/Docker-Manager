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
