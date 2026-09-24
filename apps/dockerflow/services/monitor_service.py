"""On-demand, bounded live metrics and Docker events.

No permanent daemon is started. UI explicitly requests samples; values are
estimates from a single Docker stats snapshot (not a monitoring SLA).
"""
from collections import defaultdict, deque
from datetime import datetime, timezone
from itertools import islice
from threading import RLock
from time import time
from .docker_service import docker_service

LOCK = RLock()
HISTORY = defaultdict(lambda: deque(maxlen=24))
MAX_TRACKED = 30


def _snapshot(stats):
    cpu = stats.get("cpu_stats") or {}
    previous = stats.get("precpu_stats") or {}
    current_usage = cpu.get("cpu_usage") or {}
    previous_usage = previous.get("cpu_usage") or {}
    usage = current_usage.get("total_usage", 0) - previous_usage.get("total_usage", 0)
    system = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
    online = cpu.get("online_cpus") or len(current_usage.get("percpu_usage") or []) or 1
    percent = max(0, usage / system * online * 100) if system > 0 and usage >= 0 else 0
    memory = stats.get("memory_stats") or {}
    memory_bytes = max(0, memory.get("usage", 0) - (memory.get("stats") or {}).get("cache", 0))
    limit = memory.get("limit") or 0
    nets = stats.get("networks") or {}
    return {"cpu_percent": round(percent, 2), "memory_bytes": memory_bytes,
            "memory_limit": limit,
            "memory_percent": round(memory_bytes / limit * 100, 2) if limit > 0 else 0,
            "network_rx": sum(x.get("rx_bytes", 0) for x in nets.values()),
            "network_tx": sum(x.get("tx_bytes", 0) for x in nets.values())}


def sample(limit=8):
    limit = max(1, min(int(limit), 12))
    rows = []
    containers = docker_service.client.containers.list(filters={"status": "running"})[:limit]
    now = datetime.now(timezone.utc).isoformat()
    for container in containers:
        try:
            point = _snapshot(container.stats(stream=False))
            point["time"] = now
            with LOCK:
                if len(HISTORY) >= MAX_TRACKED and container.id not in HISTORY:
                    del HISTORY[next(iter(HISTORY))]
                HISTORY[container.id].append(point)
                timeline = list(HISTORY[container.id])
            rows.append({"id": container.id, "name": container.name,
                         "current": point, "history": timeline})
        except Exception as exc:
            rows.append({"id": container.id, "name": container.name, "error": str(exc)})
    return {"samples": rows, "at": now, "note": "Amostras coletadas sob demanda"}


def events(minutes=5):
    minutes = max(1, min(int(minutes), 15))
    end = int(time())
    stream = docker_service.client.events(decode=True, since=end - minutes * 60, until=end)
    try:
        items = list(islice(stream, 50))
    finally:
        if hasattr(stream, "close"):
            stream.close()
    return [{"type": x.get("Type"), "action": x.get("Action") or x.get("status"),
             "actor": (x.get("Actor") or {}).get("Attributes", {}).get("name", ""),
             "time": x.get("time")} for x in items][-50:]
