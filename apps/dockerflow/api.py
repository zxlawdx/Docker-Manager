"""Rotas HTTP do Vela. Ações Docker nunca ocorrem por arrastar: exigir Aplicar."""
from vela.api import api
from .services.docker_service import docker_service as d
from .services.terminal_service import terminal_service as terminal
from .services import compose_service as compose
from .services.graph_service import to_compose

def safe(fn, *args):
    try:
        return fn(*args)
    except (Exception,) as exc:
        # Envelope explícito: Vela 0.2.2 devolve dict sempre com HTTP 200.
        return {"error": str(exc), "type": type(exc).__name__}

def body(context):
    return context.get("json") or {}

@api.get("/overview")
def overview():
    return d.overview()

@api.get("/containers")
def containers():
    return safe(d.containers)

@api.post("/containers/create")
def containers_create(context):
    return safe(d.create_container, body(context))

@api.post("/containers/action")
def containers_action(context):
    data = body(context)
    return safe(d.container_action, data.get("action"), data.get("id"))

@api.post("/containers/inspect")
def containers_inspect(context):
    return safe(d.inspect, body(context).get("id"))

@api.post("/containers/logs")
def containers_logs(context):
    data = body(context)
    return safe(d.logs, data.get("id"), data.get("tail", 200))

@api.post("/containers/stats")
def containers_stats(context):
    return safe(d.stats, body(context).get("id"))

@api.get("/images")
def images():
    return safe(d.images)

@api.post("/images/action")
def images_action(context):
    data = body(context)
    return safe(d.image_action, data.get("action"), data)

@api.get("/networks")
def networks():
    return safe(d.networks)

@api.post("/networks/action")
def networks_action(context):
    data = body(context)
    return safe(d.network_action, data.get("action"), data)

@api.get("/volumes")
def volumes():
    return safe(d.volumes)

@api.post("/volumes/action")
def volumes_action(context):
    data = body(context)
    return safe(d.volume_action, data.get("action"), data)

@api.post("/terminal/open")
def terminal_open(context):
    data = body(context)
    return safe(terminal.open, data.get("id"), data.get("shell", "/bin/sh"),
                data.get("user", ""))

@api.post("/terminal/poll")
def terminal_poll(context):
    return safe(terminal.poll, body(context).get("session"))

@api.post("/terminal/send")
def terminal_send(context):
    data = body(context)
    return safe(terminal.send, data.get("session"), data.get("input", ""))

@api.post("/terminal/close")
def terminal_close(context):
    return safe(terminal.close, body(context).get("session"))

@api.get("/compose/projects")
def compose_projects():
    return safe(compose.projects)

@api.post("/compose/save")
def compose_save(context):
    data = body(context)
    return safe(compose.save, data.get("name"), data.get("content"))

@api.post("/compose/load")
def compose_load(context):
    return safe(compose.load, body(context).get("name"))

@api.post("/compose/run")
def compose_run(context):
    data = body(context)
    return safe(compose.execute, data.get("name"), data.get("action"),
                data.get("content"))

@api.post("/graph/compose")
def graph_compose(context):
    return safe(lambda: {"content": to_compose(body(context))})

@api.post("/compose/dockerfile")
def compose_dockerfile(context):
    data = body(context)
    return safe(compose.save_dockerfile, data.get("name"), data.get("content"))
