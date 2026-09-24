"""Trabalhos Docker em segundo plano, com estado consultável e histórico limitado.

Não encerra uma operação que já entrou no Docker Engine quando há cancelamento.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4


class TaskService:
    def __init__(self, workers=3, max_history=80):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dockerflow")
        self.lock = RLock()
        self.jobs = {}
        self.max_history = max_history

    def submit(self, label, function, *args):
        identifier = uuid4().hex
        entry = {"id": identifier, "label": label[:90], "state": "queued",
                 "created": datetime.now(timezone.utc).isoformat(),
                 "result": None, "error": None}
        with self.lock:
            self.jobs[identifier] = entry
            self._prune()

        def runner():
            with self.lock:
                entry["state"] = "running"
            try:
                result = function(*args)
                with self.lock:
                    entry["result"] = result
                    entry["state"] = "done"
            except Exception as exc:
                with self.lock:
                    entry["error"] = str(exc)
                    entry["state"] = "failed"

        future = self.executor.submit(runner)
        with self.lock:
            entry["_future"] = future
        return {"task_id": identifier, "state": "queued"}

    def _prune(self):
        while len(self.jobs) > self.max_history:
            completed = next((key for key, job in self.jobs.items()
                              if job["state"] in ("done", "failed", "cancelled")), None)
            if completed is None:
                break
            del self.jobs[completed]

    def status(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if job is None:
                raise ValueError("Tarefa desconhecida ou expirada")
            return {key: value for key, value in job.items() if not key.startswith("_")}

    def list(self):
        with self.lock:
            return [{key: value for key, value in job.items()
                     if key not in ("result", "error") and not key.startswith("_")}
                    for job in reversed(list(self.jobs.values()))]

    def cancel(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if not job:
                raise ValueError("Tarefa não encontrada")
            future = job.get("_future")
            if future is None or not future.cancel():
                raise ValueError("A operação já iniciou: não é possível interrompê-la com segurança")
            job["state"] = "cancelled"
            return {"ok": True}


task_service = TaskService()
