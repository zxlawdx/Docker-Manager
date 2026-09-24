"""Rotas HTTP do Vela. Ações Docker nunca ocorrem por arrastar: exigir Aplicar."""
from vela.api import api
from bottle import HTTPResponse
import json
import inspect
from .services import security_service as security
from .services.task_service import task_service as tasks
from .services.docker_service import docker_service as d
from .services.terminal_service import terminal_service as terminal
from .services import compose_service as compose
from .services.graph_service import to_compose, from_compose
from .services import graph_project_service as graph_projects_service
from .services import diagnostic_service

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
    if data.get("action") in ("pull", "build"):
        return tasks.submit("Imagem: " + str(data["action"]), d.image_action, data["action"], data)
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
    if data.get("action") in ("up", "down"):
        # Persistir conteúdo na requisição principal para impedir corridas com jobs.
        return safe(lambda: (compose.save(data.get("name"), data["content"]) if
                       data.get("content") is not None else None,
                       tasks.submit("Compose " + data["action"], compose.execute,
                                    data.get("name"), data.get("action")))[1])
    return safe(compose.execute, data.get("name"), data.get("action"),
                data.get("content"))

@api.post("/graph/compose")
def graph_compose(context):
    return safe(lambda: {"content": to_compose(body(context))})

@api.post("/compose/dockerfile")
def compose_dockerfile(context):
    data = body(context)
    return safe(compose.save_dockerfile, data.get("name"), data.get("content"))

@api.get("/tasks")
def tasks_list():
    return tasks.list()

@api.post("/tasks/status")
def tasks_status(context):
    return safe(tasks.status, body(context).get("id"))

@api.post("/tasks/cancel")
def tasks_cancel(context):
    return safe(tasks.cancel, body(context).get("id"))

@api.get("/graph/projects")
def graph_projects():
    return safe(graph_projects_service.projects)

@api.post("/graph/save")
def graph_save(context):
    data = body(context)
    return safe(graph_projects_service.save, data.get("name"), data.get("graph"))

@api.post("/graph/load")
def graph_load(context):
    return safe(graph_projects_service.load, body(context).get("name"))

@api.post("/graph/drift")
def graph_drift(context):
    return safe(graph_projects_service.drift, body(context).get("graph"), d)

@api.post("/graph/from-compose")
def graph_from_compose(context):
    return safe(lambda: from_compose(body(context).get("content")))

@api.post("/diagnostics/connectivity")
def diagnostics_connectivity(context):
    data = body(context)
    return tasks.submit("Diagnóstico de rede", diagnostic_service.connectivity,
                        data.get("source"), data.get("target"))

@api.get("/diagnostics/storage")
def diagnostics_storage():
    return safe(diagnostic_service.disk_usage)


# A API compartilhada do Vela registra handlers globais. Encapsular SOMENTE
# nossas rotas e declarar explicitamente context para receber headers do Bottle.
for _route in api.routes:
    _handler = _route["handler"]
    if getattr(_handler, "__module__", "") != __name__:
        continue

    def _protected(context, handler=_handler):
        try:
            security.validate(context)
        except PermissionError as exc:
            return HTTPResponse(
                body=json.dumps({"error": str(exc)}, ensure_ascii=False),
                status=403, headers={"Content-Type": "application/json"})
        if "context" in inspect.signature(handler).parameters:
            return handler(context)
        return handler()

    _route["handler"] = _protected

