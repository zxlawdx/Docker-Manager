"""E2E opcional com Docker Engine descartável; roda somente com DOCKERFLOW_INTEGRATION=1."""
import os
import unittest
import uuid
import time
import docker
from apps.dockerflow.services.terminal_service import TerminalService
from apps.dockerflow.services.docker_service import DockerService

@unittest.skipUnless(os.getenv("DOCKERFLOW_INTEGRATION") == "1",
                     "Defina DOCKERFLOW_INTEGRATION=1 para testar com daemon Docker.")
class DockerNetworkIntegrationTests(unittest.TestCase):
    def test_integrated_terminal_exec_roundtrip(self):
        client = docker.from_env(timeout=30)
        client.images.pull("alpine:3.20")
        c = client.containers.run("alpine:3.20", command=["sleep", "180"], detach=True)
        term = TerminalService()
        session = None
        try:
            session = term.open(c.id, "/bin/sh")
            term.send(session["session"], "echo DOCKERFLOW_PTY_OK\n")
            output = ""
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and "DOCKERFLOW_PTY_OK" not in output:
                output += term.poll(session["session"])["output"]
                time.sleep(0.1)
            self.assertIn("DOCKERFLOW_PTY_OK", output)
        finally:
            if session:
                term.close(session["session"])
            c.remove(force=True)

    def test_create_connect_and_disconnect_two_containers(self):
        client=docker.from_env(timeout=40)
        client.ping()
        service=DockerService(client=client)
        suffix=uuid.uuid4().hex[:10]
        network=None
        containers=[]
        try:
            client.images.pull("alpine:3.20")
            for name in ("api","database"):
                c=client.containers.run(
                    "alpine:3.20", command=["sleep","180"],
                    name="dockerflow-ci-"+name+"-"+suffix,
                    detach=True)
                containers.append(c)
            created=service.network_action("create",{
                "name":"dockerflow-ci-net-"+suffix})
            network=created["id"]

            for c in containers:
                service.network_action("connect",{
                    "network":network,"container":c.id})

            n=client.networks.get(network)
            n.reload()
            members=n.attrs.get("Containers") or {}
            self.assertTrue(all(c.id in members for c in containers))

            reported=next(x for x in service.networks() if x["id"]==network)
            self.assertEqual(len(reported["containers"]),2)

            for c in containers:
                service.network_action("disconnect",{
                    "network":network,"container":c.id})
            n.reload()
            self.assertFalse(n.attrs.get("Containers"))
        finally:
            # Não deixa redes/contêineres presos no runner.
            for c in containers:
                try:
                    c.remove(force=True)
                except Exception:
                    pass
            if network:
                try:
                    client.networks.get(network).remove()
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
