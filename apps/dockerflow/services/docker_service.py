"""Adaptador Docker SDK. Mantém Docker fora das views Vela."""
import docker

class DockerService:
    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = docker.from_env(timeout=15)
        self._client.ping()
        return self._client

    def overview(self):
        try:
            d = self.client
            containers = d.containers.list(all=True)
            return {"online": True, "engine": d.version().get("Version", "?"),
                    "containers": len(containers),
                    "running": sum(x.status == "running" for x in containers),
                    "images": len(d.images.list()), "networks": len(d.networks.list()),
                    "volumes": len(d.volumes.list())}
        except Exception as exc:
            self._client = None
            return {"online": False, "message": str(exc)}

    def containers(self):
        data = []
        for c in self.client.containers.list(all=True):
            c.reload()
            attrs = c.attrs
            data.append({"id": c.id, "name": c.name, "status": c.status,
                         "image": attrs.get("Config", {}).get("Image", ""),
                         "ports": attrs.get("NetworkSettings", {}).get("Ports") or {},
                         "networks": list((attrs.get("NetworkSettings", {}).get("Networks") or {}).keys()),
                         "health": (attrs.get("State", {}).get("Health") or {}).get("Status", "")})
        return sorted(data, key=lambda x: x["name"])

    def container_action(self, action, identifier):
        if action not in {"start", "stop", "restart", "pause", "unpause", "remove"}:
            raise ValueError("Ação inválida")
        c = self.client.containers.get(identifier)
        if action == "remove":
            if c.status == "running":
                raise ValueError("Pare o contêiner antes de remover.")
            c.remove(force=False)
        else:
            getattr(c, action)()
        return {"ok": True}

    def create_container(self, data):
        image = data.get("image", "").strip()
        if not image:
            raise ValueError("Imagem obrigatória")
        ports = {}
        for p in data.get("ports", []):
            a, b = int(p["host"]), int(p["container"])
            if not (1 <= a <= 65535 and 1 <= b <= 65535):
                raise ValueError("Porta inválida")
            ports[str(b) + "/tcp"] = a
        volumes = {}
        for v in data.get("volumes", []):
            if v.get("source") and v.get("target", "").startswith("/"):
                volumes[v["source"]] = {"bind": v["target"], "mode": "ro" if v.get("read_only") else "rw"}
        c = self.client.containers.run(
            image, name=data.get("name") or None, detach=True, ports=ports,
            environment=data.get("environment") or {}, volumes=volumes,
            network=data.get("network") or None,
            restart_policy={"Name": data.get("restart") or "unless-stopped"})
        return {"ok": True, "id": c.id}

    def inspect(self, identifier):
        c = self.client.containers.get(identifier)
        c.reload()
        # Não enviar Config.Env; os valores podem conter credenciais.
        a = c.attrs
        return {"id": c.id, "name": c.name, "state": a.get("State"),
                "mounts": a.get("Mounts"), "networks": a.get("NetworkSettings", {}).get("Networks"),
                "ports": a.get("NetworkSettings", {}).get("Ports"),
                "restart": a.get("HostConfig", {}).get("RestartPolicy")}

    def logs(self, identifier, tail=200):
        return {"logs": self.client.containers.get(identifier).logs(
            tail=max(1, min(int(tail), 1000)), timestamps=True
        ).decode("utf-8", "replace")[-150000:]}

    def stats(self, identifier):
        s = self.client.containers.get(identifier).stats(stream=False)
        return {"cpu": s.get("cpu_stats", {}), "precpu": s.get("precpu_stats", {}),
                "memory": s.get("memory_stats", {}), "networks": s.get("networks", {})}

    def images(self):
        return [{"id": i.id, "tags": i.tags, "size": i.attrs.get("Size", 0)}
                for i in self.client.images.list()]

    def image_action(self, action, data):
        if action == "pull":
            image = self.client.images.pull(data["image"])
            return {"ok": True, "id": image.id}
        if action == "remove":
            self.client.images.remove(data["image"], force=False)
            return {"ok": True}
        if action == "build":
            from pathlib import Path
            directory = Path(data["path"]).expanduser().resolve()
            if not directory.is_dir() or not (directory / "Dockerfile").is_file():
                raise ValueError("Informe pasta local com Dockerfile")
            image, logs = self.client.images.build(path=str(directory), tag=data["tag"], rm=True)
            return {"ok": True, "id": image.id, "log": "".join(x.get("stream", "") for x in logs)[-16000:]}
        raise ValueError("Ação inválida")

    def networks(self):
        rows = []
        for n in self.client.networks.list():
            n.reload()
            a = n.attrs
            rows.append({"id": n.id, "name": n.name, "driver": a.get("Driver"),
                         "internal": a.get("Internal", False),
                         "scope": a.get("Scope"), "containers": [
                             {"id": ident, "name": info.get("Name", ""), "ip": info.get("IPv4Address", "")}
                             for ident, info in (a.get("Containers") or {}).items()]})
        return rows

    def network_action(self, action, data):
        if action == "create":
            import re
            name = str(data.get("name", ""))
            if not re.fullmatch(r"[a-zA-Z0-9][\w.-]{0,62}", name):
                raise ValueError("Nome de rede inválido")
            n = self.client.networks.create(name, driver="bridge", check_duplicate=True,
                                             internal=bool(data.get("internal")))
            return {"ok": True, "id": n.id}
        n = self.client.networks.get(data["network"])
        if action == "remove":
            if n.name in ("bridge", "host", "none"):
                raise ValueError("Rede padrão protegida")
            n.reload()
            if n.attrs.get("Containers"):
                raise ValueError("Desconecte os contêineres primeiro")
            n.remove()
        elif action in ("connect", "disconnect"):
            c = self.client.containers.get(data["container"])
            n.reload()
            is_connected = c.id in (n.attrs.get("Containers") or {})
            if action == "connect" and not is_connected:
                n.connect(c, aliases=data.get("aliases") or None)
            if action == "disconnect" and is_connected:
                if n.name in ("bridge", "host", "none"):
                    raise ValueError("Rede padrão protegida")
                n.disconnect(c, force=False)
        else:
            raise ValueError("Ação inválida")
        return {"ok": True}

    def volumes(self):
        return [{"name": v.name, "driver": v.attrs.get("Driver", "")}
                for v in self.client.volumes.list()]

    def volume_action(self, action, data):
        if action == "create":
            v = self.client.volumes.create(name=data["name"])
            return {"ok": True, "name": v.name}
        if action == "remove":
            self.client.volumes.get(data["name"]).remove(force=False)
            return {"ok": True}
        raise ValueError("Ação inválida")

docker_service = DockerService()
