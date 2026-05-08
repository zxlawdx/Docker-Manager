import grpc
from concurrent import futures
import docker
from datetime import datetime
# arquivos gerados pelo protobuf
import docker_manager_pb2 as pb2
import docker_manager_pb2_grpc as pb2_grpc


# =========================================================
# Serviço gRPC
# =========================================================
class DockerManagerService(pb2_grpc.DockerManagerServicer):

    # inicializa cliente docker
    def __init__(self):

        # conecta no daemon do docker local
        self.docker_client = docker.from_env()

        print(
            "[SERVER] Cliente Docker inicializado com sucesso",
            flush=True
        )
    # =====================================================
    # Lista todos as imagens
    # =====================================================
    def ListImages(self, request, context):
        print(
            "[SERVER] Requisição recebida -> ListImages",
            flush=True
        )

        images = self.docker_client.images.list()
        response = pb2.ImageList()

        for image in images:
            full_tag = image.tags[0] if image.tags else "<none>:<none>"
            size = str(image.attrs.get("Size", 0))
            created_raw = created = ""

            if created_raw:
                try:
                    dt = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    )

                    created = dt.strftime("%d/%m/%Y %H:%M")

                except Exception:
                    created = created_raw
            print(
                f"[SERVER] Imagem encontrada -> "
                f"{full_tag} ({image.short_id}) [{size} bytes]",
                flush=True
            )

            response.images.append(
                pb2.ImageInfo(
                    id=str(image.id),
                    tag=str(full_tag),
                    short_id=str(image.short_id),
                    disk_usage=size,
                    content_size=size,
                    created=created
                )
            )

        print(
            f"[SERVER] Total de imagens: {len(response.images)}",
            flush=True
        )

        return response
    # =====================================================
    # Lista todos os containers
    # =====================================================
    def ListContainers(self, request, context):

        print(
            "[SERVER] Requisição recebida -> ListContainers",
            flush=True
        )

        # pega todos containers
        containers = self.docker_client.containers.list(all=True)

        # resposta protobuf
        response = pb2.ContainerList()

        # adiciona containers na resposta
        for container in containers:

            print(
                f"[SERVER] Container encontrado -> "
                f"{container.name} ({container.short_id}) "
                f"[{container.status}]",
                flush=True
            )

            response.containers.append(
                pb2.ContainerInfo(
                    id=container.short_id,
                    name=container.name,
                    status=container.status
                )
            )

        print(
            f"[SERVER] Total de containers: "
            f"{len(response.containers)}",
            flush=True
        )

        return response

    # =====================================================
    # Inicia container
    # =====================================================
    
    def StartContainer(self, request, context):

        print(
            f"[SERVER] Requisição recebida -> "
            f"StartContainer ({request.id})",
            flush=True
        )

        try:

            # busca container pelo id
            container = self.docker_client.containers.get(
                request.id
            )

            # inicia container
            container.start()

            print(
                f"[SERVER] Container iniciado -> "
                f"{container.name}",
                flush=True
            )

            return pb2.ActionResponse(
                success=True,
                message="Container iniciado com sucesso"
            )

        except Exception as error:

            print(
                f"[SERVER][ERRO] {str(error)}",
                flush=True
            )

            return pb2.ActionResponse(
                success=False,
                message=str(error)
            )

    # =====================================================
    # Para container
    # =====================================================
    def StopContainer(self, request, context):

        print(
            f"[SERVER] Requisição recebida -> "
            f"StopContainer ({request.id})",
            flush=True
        )

        try:

            # busca container pelo id
            container = self.docker_client.containers.get(
                request.id
            )

            # para container
            container.stop()

            print(
                f"[SERVER] Container parado -> "
                f"{container.name}",
                flush=True
            )

            return pb2.ActionResponse(
                success=True,
                message="Container parado com sucesso"
            )

        except Exception as error:

            print(
                f"[SERVER][ERRO] {str(error)}",
                flush=True
            )

            return pb2.ActionResponse(
                success=False,
                message=str(error)
            )


    # =========================================================
    # createcontainer
    # =========================================================
    def CreateContainer(self, request, context):
            print(f"[SERVER] Requisição: CreateContainer -> Imagem: {request.image_name}", flush=True)

            try:
                # Tratamento básico de portas (Ex: recebe "8080:80", converte para {"80/tcp": 8080})
                port_bindings = None
                if hasattr(request, 'ports') and ":" in request.ports:
                    host_port, container_port = request.ports.split(':')
                    port_bindings = {f"{container_port}/tcp": int(host_port)}

                # O Docker SDK baixa a imagem se não existir e cria o container
                container = self.docker_client.containers.run(
                    image=request.image_name,
                    name=request.container_name if request.container_name else None,
                    ports=port_bindings,
                    detach=True
                )

                return pb2.ActionResponse(
                    success=True, 
                    message=f"Container {container.name} criado com sucesso!"
                )

            except Exception as error:
                print(f"[SERVER][ERRO] {str(error)}", flush=True)
                return pb2.ActionResponse(success=False, message=str(error))
            
def serve():

    # host e porta
    HOST = "localhost"
    PORT = 50051

    print(
        "[SERVER] Inicializando servidor gRPC...",
        flush=True
    )

    # cria pool de threads
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10)
    )

    # registra serviço no servidor
    pb2_grpc.add_DockerManagerServicer_to_server(
        DockerManagerService(),
        server
    )

    # define porta
    server.add_insecure_port(f"[::]:{PORT}")

    # inicia servidor
    server.start()

    print(
        f"[SERVER] Servidor rodando em "
        f"{HOST}:{PORT}",
        flush=True
    )

    print(
        "[SERVER] Aguardando requisições...",
        flush=True
    )

    # mantém servidor vivo
    server.wait_for_termination()


# =========================================================
# Entry point
# =========================================================
if __name__ == "__main__":

    print(
        "[SERVER] Boot do servidor iniciado",
        flush=True
    )

    serve()