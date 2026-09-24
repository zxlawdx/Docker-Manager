"""E2E opcional com Docker Engine descartável; roda somente com DOCKERFLOW_INTEGRATION=1."""
import os
import unittest
import uuid
import docker
from apps.dockerflow.services.docker_service import DockerService

@unittest.skipUnless(os.getenv("DOCKERFLOW_INTEGRATION") == "1",
                     "Defina DOCKERFLOW_INTEGRATION=1 para testar com daemon Docker.")
class DockerNetworkIntegrationTests(unittest.TestCase):
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
