class Container:
    def __init__(self, container_id, name, image, status, ports=None):
        self.container_id = container_id
        self.name = name
        self.image = image
        self.status = status
        self.ports = ports if ports else []

    def start(self):
        print(f"Iniciando container '{self.name}'...")

    def stop(self):
        print(f"Parando container '{self.name}'...")

    def restart(self):
        print(f"Reiniciando container '{self.name}'...")

    def info(self):
        return {
            "id": self.container_id,
            "name": self.name,
            "image": self.image,
            "status": self.status,
            "ports": self.ports
        }

    def __str__(self):
        portas = ", ".join(self.ports) if self.ports else "Sem portas expostas"

        return (
            f"Container(\n"
            f"  ID: {self.container_id}\n"
            f"  Nome: {self.name}\n"
            f"  Imagem: {self.image}\n"
            f"  Status: {self.status}\n"
            f"  Portas: {portas}\n"
            f")"
        )