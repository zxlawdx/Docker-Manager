"""Read-only Docker security configuration heuristics, no env secrets."""
from .docker_service import docker_service


def inspect_containers(client=None):
    client = client or docker_service.client
    findings = []
    for container in client.containers.list(all=True):
        container.reload()
        attrs = container.attrs
        host = attrs.get("HostConfig") or {}
        config = attrs.get("Config") or {}
        settings = attrs.get("NetworkSettings") or {}
        notes = []
        if host.get("Privileged"):
            notes.append("Container privilegiado: confirme a necessidade.")
        mounts = attrs.get("Mounts") or []
        if any(m.get("Source") in ("/var/run/docker.sock", "/run/docker.sock") or
               m.get("Destination") in ("/var/run/docker.sock", "/run/docker.sock")
               for m in mounts):
            notes.append("Socket Docker montado: acesso potencialmente privilegiado.")
        if any(binding.get("HostIp") in ("0.0.0.0", "::", "")
               for bindings in (settings.get("Ports") or {}).values()
               for binding in bindings or []):
            notes.append("Porta publicada em todas as interfaces.")
        if str(config.get("User") or "") in ("", "root", "0"):
            notes.append("Usuário não privilegiado não foi explicitamente definido na configuração.")
        if "no-new-privileges:true" not in (host.get("SecurityOpt") or []):
            notes.append("no-new-privileges não está explicitamente habilitado.")
        if "SYS_ADMIN" in (host.get("CapAdd") or []):
            notes.append("Capability SYS_ADMIN adicional.")
        findings.append({"id": container.id, "name": container.name,
                         "status": container.status, "notes": notes})
    return {"containers": findings, "note":
            "Sinais de configuração que exigem revisão; nenhum item prova vulnerabilidade por si só."}


def unused_volumes(client=None):
    client = client or docker_service.client
    referenced = set()
    for container in client.containers.list(all=True):
        container.reload()
        for mount in container.attrs.get("Mounts") or []:
            if mount.get("Type") == "volume" and mount.get("Name"):
                referenced.add(mount["Name"])
    return [{"name": volume.name, "driver": volume.attrs.get("Driver", "")}
            for volume in client.volumes.list() if volume.name not in referenced]
