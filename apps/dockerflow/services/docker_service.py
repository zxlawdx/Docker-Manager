"""Adaptador Docker SDK. Mantém Docker fora das views Vela."""
import docker
import ipaddress
from docker.types import IPAMConfig, IPAMPool

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
        restart = data.get("restart") or "unless-stopped"
        if restart not in {"no", "always", "unless-stopped", "on-failure"}:
            raise ValueError("Política de restart desconhecida")
        extra = {}
        if data.get("cpus") not in (None, ""):
            cpus = float(data["cpus"])
            if not 0.01 <= cpus <= 128:
                raise ValueError("Limite de CPU fora do intervalo")
            extra["nano_cpus"] = int(cpus * 1_000_000_000)
        if data.get("memory_mb") not in (None, ""):
            memory_mb = int(data["memory_mb"])
            if not 32 <= memory_mb <= 1048576:
                raise ValueError("Memória: entre 32 MiB e 1 TiB")
            extra["mem_limit"] = memory_mb * 1024 * 1024
        if data.get("read_only"):
            extra["read_only"] = True
        if data.get("no_new_privileges"):
            extra["security_opt"] = ["no-new-privileges:true"]
        ports = {}
        for p in data.get("ports", []):
            a, b = int(p["host"]), int(p["container"])
            if not (1 <= a <= 65535 and 1 <= b <= 65535):
                raise ValueError("Porta inválida")
            protocol = p.get("protocol") or "tcp"
            if protocol not in ("tcp", "udp"):
                raise ValueError("Protocolo inválido")
            ports[str(b) + "/" + protocol] = a
        volumes = {}
        for v in data.get("volumes", []):
            if not isinstance(v, dict) or not isinstance(v.get("source"), str) or not v["source"]:
                raise ValueError("Origem do volume é obrigatória")
            if not isinstance(v.get("target"), str) or not v["target"].startswith("/"):
                raise ValueError("Destino do volume deve ser absoluto")
            mode = v.get("mode") or ("ro" if v.get("read_only") else "rw")
            if mode not in ("ro", "rw"):
                raise ValueError("Modo de montagem inválido")
            volumes[v["source"]] = {"bind": v["target"], "mode": mode}
        if data.get("dns"):
            servers = data["dns"]
            if not isinstance(servers, list) or len(servers) > 4:
                raise ValueError("DNS: até quatro endereços IP")
            extra["dns"] = [str(ipaddress.ip_address(ip)) for ip in servers]
        if data.get("command") is not None:
            command = data["command"]
            if (not isinstance(command, list) or not 1 <= len(command) <= 30 or
                any(not isinstance(x, str) or not x or len(x) > 200 for x in command)):
                raise ValueError("Comando deve ser uma lista de até 30 argumentos")
            extra["command"] = command
        c = self.client.containers.run(
            image, name=data.get("name") or None, detach=True, ports=ports,
            environment=data.get("environment") or {}, volumes=volumes,
            network=data.get("network") or None,
            restart_policy={"Name": restart}, **extra)
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

    def processes(self, identifier):
        """Processos sem argumentos/comandos, pois podem revelar segredos."""
        c = self.client.containers.get(identifier)
        if c.status != "running":
            raise ValueError("O container precisa estar em execução")
        output = c.top()
        titles = output.get("Titles") or []
        columns = [(i, name) for i, name in enumerate(titles)
                   if str(name).upper() in {"PID", "PPID", "UID", "USER", "TIME", "%CPU", "%MEM", "STAT"}]
        processes = [{name: str(row[i])[:120] for i, name in columns if i < len(row)}
                     for row in (output.get("Processes") or [])[:150]]
        return {"container": c.name, "columns": [name for _, name in columns],
                "processes": processes, "note": "COMMAND/ARGS omitidos para proteger segredos."}

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
        if action == "history":
            image = self.client.images.get(data["image"])
            # Evita CreatedBy: instruções de build podem conter credenciais.
            return {"history": [{"id": x.get("Id"), "created": x.get("Created"),
                                 "size": x.get("Size")} for x in image.history()]}
        if action == "tag":
            import re
            name, tag = str(data.get("repository") or ""), str(data.get("tag") or "latest")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.\\/-]{0,180}", name):
                raise ValueError("Repositório de imagem inválido")
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
                raise ValueError("Tag de imagem inválida")
            return {"ok": self.client.images.get(data["image"]).tag(name, tag=tag)}
        if action == "prune-preview":
            dangling = self.client.images.list(filters={"dangling": True})
            return {"count": len(dangling),
                    "images": [{"id": x.id, "size": x.attrs.get("Size", 0)} for x in dangling],
                    "notice": "Camadas compartilhadas: soma de tamanhos não é espaço recuperável."}
        if action == "prune":
            result = self.client.images.prune(filters={"dangling": True})
            return {"ok": True, "deleted": result.get("ImagesDeleted") or [],
                    "space_reclaimed": result.get("SpaceReclaimed", 0)}
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
                         "scope": a.get("Scope"), "ipam": a.get("IPAM") or {},
                         "ipv6": a.get("EnableIPv6", False), "containers": [
                             {"id": ident, "name": info.get("Name", ""), "ip": info.get("IPv4Address", ""),
                              "ipv6": info.get("IPv6Address", "")}
                             for ident, info in (a.get("Containers") or {}).items()]})
        return rows

    def network_action(self, action, data):
        if action == "create":
            import re
            name = str(data.get("name", ""))
            if not re.fullmatch(r"[a-zA-Z0-9][\w.-]{0,62}", name):
                raise ValueError("Nome de rede inválido")
            subnet = str(data.get("subnet") or "").strip()
            gateway = str(data.get("gateway") or "").strip()
            subnet6 = str(data.get("ipv6_subnet") or "").strip()
            gateway6 = str(data.get("ipv6_gateway") or "").strip()
            kwargs = {"driver": "bridge", "check_duplicate": True,
                      "internal": bool(data.get("internal"))}
            if gateway and not subnet:
                raise ValueError("Defina a sub-rede antes do gateway")
            pools = []
            if subnet:
                network = ipaddress.ip_network(subnet, strict=True)
                if network.version != 4:
                    raise ValueError("A primeira sub-rede deve ser IPv4")
                if gateway and ipaddress.ip_address(gateway) not in network:
                    raise ValueError("Gateway fora da sub-rede")
                pools.append(IPAMPool(subnet=str(network), gateway=gateway or None))
            if gateway6 and not subnet6:
                raise ValueError("Defina a sub-rede IPv6 antes do gateway IPv6")
            if subnet6:
                network6 = ipaddress.ip_network(subnet6, strict=True)
                if network6.version != 6:
                    raise ValueError("A sub-rede secundária deve ser IPv6")
                if gateway6 and ipaddress.ip_address(gateway6) not in network6:
                    raise ValueError("Gateway IPv6 fora da sub-rede")
                pools.append(IPAMPool(subnet=str(network6), gateway=gateway6 or None))
                kwargs["enable_ipv6"] = True
            elif data.get("enable_ipv6"):
                kwargs["enable_ipv6"] = True
            if pools:
                kwargs["ipam"] = IPAMConfig(pool_configs=pools)
            n = self.client.networks.create(name, **kwargs)
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
                import re
                aliases = data.get("aliases") or []
                if (not isinstance(aliases, list) or len(aliases) > 8 or
                    any(not isinstance(a, str) or not re.fullmatch(
                        r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}", a) or ".." in a for a in aliases)):
                    raise ValueError("Aliases inválidos (até oito nomes DNS)")
                ipv4 = str(data.get("ipv4_address") or "").strip()
                ipv6 = str(data.get("ipv6_address") or "").strip()
                for address, version in ((ipv4, 4), (ipv6, 6)):
                    if address and ipaddress.ip_address(address).version != version:
                        raise ValueError("Endereço IP incompatível com IPv4/IPv6")
                n.connect(c, aliases=aliases or None, ipv4_address=ipv4 or None,
                          ipv6_address=ipv6 or None)
            if action == "disconnect" and is_connected:
                if n.name in ("bridge", "host", "none"):
                    raise ValueError("Rede padrão protegida")
                n.disconnect(c, force=False)
        else:
            raise ValueError("Ação inválida")
        return {"ok": True}

    def _volume_references(self):
        references = {}
        for c in self.client.containers.list(all=True):
            for mount in c.attrs.get("Mounts") or []:
                if mount.get("Type") == "volume" and mount.get("Name"):
                    references.setdefault(mount["Name"], set()).add(c.name)
        return references

    def volumes(self):
        references = self._volume_references()
        return [{"name": v.name, "driver": v.attrs.get("Driver", ""),
                 "containers": sorted(references.get(v.name, set()))}
                for v in self.client.volumes.list()]

    def volume_action(self, action, data):
        if action == "create":
            v = self.client.volumes.create(name=data["name"])
            return {"ok": True, "name": v.name}
        if action == "inspect":
            v = self.client.volumes.get(data["name"])
            return {"name": v.name, "driver": v.attrs.get("Driver", ""),
                    "scope": v.attrs.get("Scope", ""), "mountpoint": v.attrs.get("Mountpoint", ""),
                    "containers": sorted(self._volume_references().get(v.name, set())),
                    "note": "Options/labels omitidos: podem armazenar credenciais."}
        if action == "remove":
            if self._volume_references().get(data["name"]):
                raise ValueError("Volume referenciado por containers, inclusive parados")
            self.client.volumes.get(data["name"]).remove(force=False)
            return {"ok": True}
        raise ValueError("Ação inválida")

docker_service = DockerService()
